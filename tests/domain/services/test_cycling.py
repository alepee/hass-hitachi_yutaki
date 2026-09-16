"""Unit tests for the compressor short-cycling detection service."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from custom_components.hitachi_yutaki.adapters.storage.in_memory import InMemoryStorage
from custom_components.hitachi_yutaki.domain.models.cycling import CyclingInput
from custom_components.hitachi_yutaki.domain.services.cycling import (
    ALERT_PERSIST_DAYS,
    DEBOUNCE_S,
    HISTORY_DAYS,
    MIN_CYCLES_PER_DAY,
    STATUS_ALERT,
    STATUS_LEARNING,
    STATUS_OK,
    STATUS_WATCH,
    CyclingMonitor,
)

START = datetime(2026, 1, 5, 6, 0, 0)
POLL = timedelta(seconds=5)


def _monitor() -> CyclingMonitor:
    """Return a monitor backed by an in-memory daily-aggregate store."""
    return CyclingMonitor(InMemoryStorage(max_len=HISTORY_DAYS))


def _input(
    *, running: bool | None = True, mode: str | None = "heating", reliable: bool = True
) -> CyclingInput:
    """Build one poll of cycling signals."""
    return CyclingInput(
        operation_mode=mode, compressor_running=running, data_reliable=reliable
    )


def _feed(
    monitor: CyclingMonitor,
    *,
    at: datetime,
    running: bool,
    duration: timedelta,
    mode: str | None = "heating",
    reliable: bool = True,
) -> datetime:
    """Hold one compressor state for ``duration``, polling every 5 seconds.

    Returns the timestamp just past the end of the held period.
    """
    now = at
    end = at + duration
    while now < end:
        monitor.update(
            _input(running=running, mode=mode, reliable=reliable), timestamp=now
        )
        now += POLL
    return now


def _run_cycles(
    monitor: CyclingMonitor,
    *,
    start: datetime,
    count: int,
    run: timedelta,
    rest: timedelta,
    mode: str | None = "heating",
) -> datetime:
    """Feed ``count`` on/off cycles of the given shape."""
    now = start
    for _ in range(count):
        now = _feed(monitor, at=now, running=True, duration=run, mode=mode)
        now = _feed(monitor, at=now, running=False, duration=rest, mode=mode)
    return now


def _end_day(monitor: CyclingMonitor, *, after: datetime) -> datetime:
    """Push the monitor into the next day so the running day is flushed."""
    next_day = datetime.combine(
        (after + timedelta(days=1)).date(), datetime.min.time()
    ) + timedelta(hours=6)
    monitor.update(_input(running=False), timestamp=next_day)
    return next_day


def test_starts_in_learning_with_no_valid_day() -> None:
    """Before any day is aggregated the verdict is `learning`."""
    monitor = _monitor()
    status = monitor.get_status()
    assert status.status == STATUS_LEARNING
    assert status.valid_days == 0


def test_debounce_ignores_a_blip() -> None:
    """A state change shorter than the debounce window is not a transition."""
    monitor = _monitor()
    now = _feed(monitor, at=START, running=True, duration=timedelta(minutes=5))
    # Off for less than DEBOUNCE_S, then running again.
    now = _feed(
        monitor, at=now, running=False, duration=timedelta(seconds=DEBOUNCE_S - 10)
    )
    _feed(monitor, at=now, running=True, duration=timedelta(minutes=5))

    assert monitor.get_status().cycles_today == 0


def test_healthy_long_cycles_are_ok() -> None:
    """Long cycles produce a valid day that is not faulted.

    One extra cycle is fed because the very first observed state cannot be
    counted as a start: the monitor did not see the transition into it, so it
    has no timestamp to measure a period from.
    """
    monitor = _monitor()
    now = _run_cycles(
        monitor,
        start=START,
        count=MIN_CYCLES_PER_DAY + 2,
        run=timedelta(minutes=25),
        rest=timedelta(minutes=20),
    )
    _end_day(monitor, after=now)

    status = monitor.get_status()
    assert status.valid_days == 1
    assert status.status == STATUS_OK
    assert status.alert_streak == 0


def test_short_cycling_day_raises_watch() -> None:
    """A single faulted day is a watch, not yet an alert."""
    monitor = _monitor()
    now = _run_cycles(
        monitor,
        start=START,
        count=8,
        run=timedelta(minutes=4),
        rest=timedelta(minutes=4),
    )
    _end_day(monitor, after=now)

    status = monitor.get_status()
    assert status.valid_days == 1
    assert status.alert_streak == 1
    assert status.status == STATUS_WATCH


def test_sustained_short_cycling_raises_alert() -> None:
    """The alert needs the fault to hold for ALERT_PERSIST_DAYS days."""
    monitor = _monitor()
    day_start = START
    for _ in range(ALERT_PERSIST_DAYS):
        end = _run_cycles(
            monitor,
            start=day_start,
            count=8,
            run=timedelta(minutes=4),
            rest=timedelta(minutes=4),
        )
        day_start = _end_day(monitor, after=end)

    status = monitor.get_status()
    assert status.alert_streak == ALERT_PERSIST_DAYS
    assert status.status == STATUS_ALERT


def test_recovery_clears_the_streak() -> None:
    """One healthy day resets the streak, so the alert clears on its own."""
    monitor = _monitor()
    day_start = START
    for _ in range(ALERT_PERSIST_DAYS):
        end = _run_cycles(
            monitor,
            start=day_start,
            count=8,
            run=timedelta(minutes=4),
            rest=timedelta(minutes=4),
        )
        day_start = _end_day(monitor, after=end)
    assert monitor.get_status().status == STATUS_ALERT

    end = _run_cycles(
        monitor,
        start=day_start,
        count=MIN_CYCLES_PER_DAY + 2,
        run=timedelta(minutes=25),
        rest=timedelta(minutes=20),
    )
    _end_day(monitor, after=end)

    status = monitor.get_status()
    assert status.alert_streak == 0
    assert status.status == STATUS_OK


def test_dhw_cycles_are_not_counted() -> None:
    """Only space heating counts: a DHW cycle chain never produces a valid day."""
    monitor = _monitor()
    now = _run_cycles(
        monitor,
        start=START,
        count=8,
        run=timedelta(minutes=4),
        rest=timedelta(minutes=4),
        mode="dhw",
    )
    _end_day(monitor, after=now)

    assert monitor.get_status().valid_days == 0


def test_defrost_breaks_the_cycle_chain() -> None:
    """Defrost transitions are not cycling: unreliable data breaks the chain.

    A defrost stops and restarts the compressor for reasons that have nothing
    to do with cycling, so the same on/off shape must produce cycles when the
    data is reliable and none when it is not.
    """
    reliable = _monitor()
    _run_cycles(
        reliable,
        start=START,
        count=8,
        run=timedelta(minutes=4),
        rest=timedelta(minutes=4),
    )
    assert reliable.get_status().cycles_today > 0

    unreliable = _monitor()
    now = START
    for _ in range(8):
        now = _feed(
            unreliable,
            at=now,
            running=True,
            duration=timedelta(minutes=4),
            reliable=False,
        )
        now = _feed(
            unreliable,
            at=now,
            running=False,
            duration=timedelta(minutes=4),
            reliable=False,
        )
    assert unreliable.get_status().cycles_today == 0


def test_data_hole_does_not_invent_a_transition() -> None:
    """A gap in the polls drops the state machine instead of faking a cycle."""
    monitor = _monitor()
    now = _feed(monitor, at=START, running=True, duration=timedelta(minutes=10))
    # One poll, hours later, with the compressor off.
    monitor.update(_input(running=False), timestamp=now + timedelta(hours=3))
    # Then a normal run resumes.
    _feed(
        monitor,
        at=now + timedelta(hours=3, seconds=5),
        running=True,
        duration=timedelta(minutes=10),
    )

    # The gap must not have produced a cycle period.
    assert monitor.get_status().cycles_today == 0


def test_serialize_restore_round_trip() -> None:
    """A serialized snapshot restores the streak and the daily aggregates."""
    monitor = _monitor()
    day_start = START
    for _ in range(2):
        end = _run_cycles(
            monitor,
            start=day_start,
            count=8,
            run=timedelta(minutes=4),
            rest=timedelta(minutes=4),
        )
        day_start = _end_day(monitor, after=end)

    snapshot = monitor.serialize()
    restored = _monitor()
    restored.restore(snapshot)

    assert restored.get_status().valid_days == monitor.get_status().valid_days
    assert restored.get_status().alert_streak == monitor.get_status().alert_streak
    assert restored.serialize() == snapshot


def test_restore_rejects_a_malformed_snapshot() -> None:
    """A corrupt payload raises and leaves the monitor untouched."""
    monitor = _monitor()
    with pytest.raises(ValueError, match="Malformed cycling snapshot"):
        monitor.restore({"aggregates": [{"day": "not-a-date"}]})
    assert monitor.get_status().status == STATUS_LEARNING


def test_reset_clears_everything() -> None:
    """Reset drops the aggregates and the streak."""
    monitor = _monitor()
    now = _run_cycles(
        monitor,
        start=START,
        count=8,
        run=timedelta(minutes=4),
        rest=timedelta(minutes=4),
    )
    _end_day(monitor, after=now)
    assert monitor.get_status().valid_days == 1

    monitor.reset()
    status = monitor.get_status()
    assert status.valid_days == 0
    assert status.alert_streak == 0
    assert status.status == STATUS_LEARNING
