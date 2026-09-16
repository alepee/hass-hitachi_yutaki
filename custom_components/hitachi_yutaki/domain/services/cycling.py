"""Compressor short-cycling detection service.

Detects a compressor that starts and stops too often in space heating, which
wears the machine, costs seasonal efficiency, and points at an oversized unit,
a missing buffer volume, or a heating curve set too high.

Pure business logic, isolated from Home Assistant. Mirrors the refrigerant
service in shape (per-day aggregates, persisted state, an ENUM verdict), but
**not** in method: short cycling is a *stable state*, not a slow drift, so
there is no learned baseline here. A baseline would learn the fault and never
report it (fleet evidence: inter-unit over intra-unit dispersion ratio of 3.3
in heating, so the between-installation spread dominates by far).

Thresholds are absolute and were calibrated by replaying the telemetry archive
rather than taken from the literature. The usual "3 starts per hour" rule of
thumb flags a third of real installations, because these machines genuinely run
short cycles: the fleet median run is 6.7 min against a 10-15 min target. Only
the conjunction of a high start count *and* a short cycle period separates the
tail of the distribution from the bulk of it.

See ``docs/reference/cycling-monitoring.md`` for the full rationale.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import median
from typing import Any

from ..models.cycling import CyclingDailyAggregate, CyclingInput, CyclingStatus
from ..models.operation import MODE_HEATING
from ..ports.storage import Storage

# Transition detection
DEBOUNCE_S = 30.0  # a state change must hold this long to count as a transition
GAP_FACTOR = 4  # a poll gap beyond this many median intervals is a data hole
GAP_FLOOR_S = 90.0  # ...but never treat anything under this as a hole
_INTERVAL_SAMPLES = 50  # rolling window used to estimate the poll interval

# Daily aggregation
MIN_CYCLES_PER_DAY = 4  # fewer cycles than this cannot characterise a day
HISTORY_DAYS = 45  # rolling window of daily aggregates
PEAK_WINDOW = timedelta(minutes=60)

# Fault criteria (absolute, calibrated on fleet data). Both must hold.
PEAK_STARTS_THRESHOLD = 6  # starts within any 60-minute window
PERIOD_THRESHOLD_MIN = 15.0  # median cycle period, minutes

# Consecutive faulted days before a repair issue is raised
ALERT_PERSIST_DAYS = 3

# Status values (also the ENUM options of the diagnostic sensor)
STATUS_LEARNING = "learning"
STATUS_OK = "ok"
STATUS_WATCH = "watch"
STATUS_ALERT = "alert"


class CyclingMonitor:
    """Counts space-heating compressor cycles and flags sustained short cycling.

    The service is independent of Home Assistant and infrastructure concerns.
    Daily aggregates live in the injected ``Storage``; the intra-day transition
    buffers are transient and deliberately not persisted, because a restart
    mid-day cannot reconstruct the transitions it did not see.
    """

    def __init__(self, storage: Storage[CyclingDailyAggregate]) -> None:
        """Initialize the monitor with a bounded daily-aggregate storage."""
        self._storage = storage
        self._alert_streak = 0

        # Transition state machine (transient).
        self._current_day: date | None = None
        self._state: bool | None = None
        self._pending_state: bool | None = None
        self._pending_since: datetime | None = None
        self._last_seen: datetime | None = None
        self._intervals: list[float] = []

        # Intra-day measurements (transient).
        self._starts: list[datetime] = []
        self._periods: list[float] = []
        self._runs: list[float] = []
        self._last_start: datetime | None = None
        self._run_started: datetime | None = None
        self._regime_broken = True

    def update(self, data: CyclingInput, *, timestamp: datetime | None = None) -> bool:
        """Feed one poll of signals.

        Returns ``True`` when a daily aggregate was just flushed (a cue for the
        adapter to persist the serialized state).
        """
        now = timestamp or datetime.now()

        flushed = False
        today = now.date()
        if self._current_day is None:
            self._current_day = today
        elif today != self._current_day:
            flushed = self._flush_day()
            self._current_day = today

        if self._note_gap(now):
            # A hole in the data looks exactly like a long off period. Drop the
            # state machine rather than invent a transition across the gap.
            self._reset_transition_state()

        if data.compressor_running is None:
            return flushed

        # A defrost stops and restarts the compressor for reasons unrelated to
        # cycling, and so does any regime other than space heating. Both break
        # the current cycle chain instead of contributing to it.
        if not data.data_reliable or data.operation_mode != MODE_HEATING:
            self._regime_broken = True
            self._state = data.compressor_running
            self._pending_state = None
            self._pending_since = None
            return flushed

        self._observe_state(data.compressor_running, now)
        return flushed

    def get_status(self) -> CyclingStatus:
        """Return the current detector verdict."""
        return self._evaluate()

    def serialize(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the persistent state."""
        return {
            "alert_streak": self._alert_streak,
            "aggregates": [
                {
                    "day": aggregate.day.isoformat(),
                    "cycles": aggregate.cycles,
                    "median_period": aggregate.median_period,
                    "peak_starts": aggregate.peak_starts,
                    "median_run": aggregate.median_run,
                    "faulted": aggregate.faulted,
                }
                for aggregate in self._storage.get_all()
            ],
        }

    def restore(self, state: dict[str, Any] | None) -> None:
        """Restore persistent state from a serialized snapshot.

        The snapshot is validated in full *before* any state is mutated, so a
        malformed payload raises ``ValueError`` and leaves the monitor
        untouched rather than half-loading. Restoring a well-formed snapshot
        onto any monitor is idempotent.
        """
        if not state:
            return

        try:
            new_alert_streak = int(state.get("alert_streak", 0))
            new_aggregates = [
                CyclingDailyAggregate(
                    day=date.fromisoformat(item["day"]),
                    cycles=int(item["cycles"]),
                    median_period=float(item["median_period"]),
                    peak_starts=int(item["peak_starts"]),
                    median_run=float(item["median_run"]),
                    faulted=bool(item["faulted"]),
                )
                for item in state.get("aggregates", [])
            ]
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            raise ValueError("Malformed cycling snapshot") from err

        self._current_day = None
        self._reset_transition_state()
        self._reset_day_buffers()
        while len(self._storage):
            self._storage.popleft()

        self._alert_streak = new_alert_streak
        for aggregate in new_aggregates:
            self._storage.append(aggregate)

    def reset(self) -> None:
        """Clear all state (used after the installation has been serviced)."""
        self._alert_streak = 0
        self._current_day = None
        self._reset_transition_state()
        self._reset_day_buffers()
        while len(self._storage):
            self._storage.popleft()

    def _note_gap(self, now: datetime) -> bool:
        """Track the poll interval and report whether this poll follows a hole."""
        last = self._last_seen
        self._last_seen = now
        if last is None:
            return False

        delta = (now - last).total_seconds()
        if delta < 0:
            # Clock went backwards (DST, NTP step). Not a hole, but the
            # interval estimate must not absorb a negative value.
            return True

        threshold = max(GAP_FLOOR_S, GAP_FACTOR * self._median_interval())
        self._intervals.append(delta)
        if len(self._intervals) > _INTERVAL_SAMPLES:
            self._intervals.pop(0)
        return delta > threshold

    def _median_interval(self) -> float:
        """Return the median poll interval seen so far, in seconds."""
        if not self._intervals:
            return 0.0
        return median(self._intervals)

    def _observe_state(self, running: bool, now: datetime) -> None:
        """Advance the debounced transition state machine."""
        if self._state is None:
            self._state = running
            return

        if running == self._state:
            self._pending_state = None
            self._pending_since = None
            return

        if self._pending_state != running:
            self._pending_state = running
            self._pending_since = now
            return

        assert self._pending_since is not None
        if (now - self._pending_since).total_seconds() < DEBOUNCE_S:
            return

        # The change held long enough: commit it, dated at the moment it was
        # first seen rather than when it was confirmed.
        changed_at = self._pending_since
        self._state = running
        self._pending_state = None
        self._pending_since = None

        if running:
            self._record_start(changed_at)
        else:
            self._record_stop(changed_at)

    def _record_start(self, when: datetime) -> None:
        """Record a compressor start and the period since the previous one."""
        if self._last_start is not None and not self._regime_broken:
            period = (when - self._last_start).total_seconds() / 60
            if period > 0:
                self._periods.append(period)
        self._starts.append(when)
        self._last_start = when
        self._run_started = when
        self._regime_broken = False

    def _record_stop(self, when: datetime) -> None:
        """Record the duration of the run that just ended."""
        started = self._run_started
        if started is not None:
            run = (when - started).total_seconds() / 60
            if run > 0:
                self._runs.append(run)
        self._run_started = None

    def _peak_starts(self) -> int:
        """Return the highest number of starts within any 60-minute window."""
        if not self._starts:
            return 0
        peak = 0
        left = 0
        for right, start in enumerate(self._starts):
            while start - self._starts[left] > PEAK_WINDOW:
                left += 1
            peak = max(peak, right - left + 1)
        return peak

    def _flush_day(self) -> bool:
        """Aggregate the finished day and update the alert streak."""
        cycles = len(self._periods)
        added = False
        if cycles >= MIN_CYCLES_PER_DAY and self._current_day is not None:
            period = median(self._periods)
            peak = self._peak_starts()
            faulted = period <= PERIOD_THRESHOLD_MIN and peak >= PEAK_STARTS_THRESHOLD
            self._storage.append(
                CyclingDailyAggregate(
                    day=self._current_day,
                    cycles=cycles,
                    median_period=period,
                    peak_starts=peak,
                    median_run=median(self._runs) if self._runs else 0.0,
                    faulted=faulted,
                )
            )
            added = True
            self._alert_streak = self._alert_streak + 1 if faulted else 0

        self._reset_day_buffers()
        return added

    def _reset_day_buffers(self) -> None:
        """Clear the transient intra-day measurements."""
        self._starts = []
        self._periods = []
        self._runs = []
        self._last_start = None
        self._run_started = None
        self._regime_broken = True

    def _reset_transition_state(self) -> None:
        """Drop the debounced state machine without inventing a transition."""
        self._state = None
        self._pending_state = None
        self._pending_since = None
        self._regime_broken = True

    def _evaluate(self) -> CyclingStatus:
        """Derive the current verdict from stored days and the running day."""
        aggregates = self._storage.get_all()
        valid_days = len(aggregates)
        cycles_today = len(self._periods)
        period_today = median(self._periods) if self._periods else None
        run_today = median(self._runs) if self._runs else None
        peak_today = self._peak_starts() if self._starts else None
        last_valid_day = aggregates[-1].day if aggregates else None

        if valid_days == 0:
            return CyclingStatus(
                status=STATUS_LEARNING,
                cycles_today=cycles_today,
                peak_starts_today=peak_today,
                median_period_today=period_today,
                median_run_today=run_today,
                valid_days=valid_days,
                alert_streak=self._alert_streak,
                last_valid_day=last_valid_day,
            )

        if self._alert_streak >= ALERT_PERSIST_DAYS:
            status = STATUS_ALERT
        elif self._alert_streak > 0 or self._today_faulted(period_today, peak_today):
            status = STATUS_WATCH
        else:
            status = STATUS_OK

        return CyclingStatus(
            status=status,
            cycles_today=cycles_today,
            peak_starts_today=peak_today,
            median_period_today=period_today,
            median_run_today=run_today,
            valid_days=valid_days,
            alert_streak=self._alert_streak,
            last_valid_day=last_valid_day,
        )

    def _today_faulted(self, period: float | None, peak: int | None) -> bool:
        """Return whether the running day already meets both fault criteria."""
        if period is None or peak is None:
            return False
        if len(self._periods) < MIN_CYCLES_PER_DAY:
            return False
        return period <= PERIOD_THRESHOLD_MIN and peak >= PEAK_STARTS_THRESHOLD
