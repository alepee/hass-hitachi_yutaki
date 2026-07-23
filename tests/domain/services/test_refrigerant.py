"""Unit tests for the refrigerant-circuit anomaly detection service."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import itertools

import pytest

from custom_components.hitachi_yutaki.adapters.storage.in_memory import InMemoryStorage
from custom_components.hitachi_yutaki.domain.models.refrigerant import RefrigerantInput
from custom_components.hitachi_yutaki.domain.services import refrigerant as refr
from custom_components.hitachi_yutaki.domain.services.refrigerant import (
    BASELINE_DAYS,
    HISTORY_DAYS,
    MIN_SAMPLES_PER_DAY,
    STATUS_ALERT,
    STATUS_LEARNING,
    STATUS_OK,
    STATUS_WATCH,
    RefrigerantMonitor,
)


@pytest.fixture(autouse=True)
def _fake_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Advance the throttle clock by one interval on every call.

    The service records at most one sample per SAMPLE_MIN_INTERVAL_S. Returning a
    value one interval later on each call lets tests feed many samples per day.
    """
    counter = itertools.count(
        start=refr.SAMPLE_MIN_INTERVAL_S, step=refr.SAMPLE_MIN_INTERVAL_S
    )
    monkeypatch.setattr(refr, "time", lambda: float(next(counter)))


def _make_input(
    *,
    mode: str | None = "heating",
    freq: float | None = 50.0,
    sh: float = 5.0,
    te: float | None = -5.0,
    evo: float = 40.0,
    outdoor: float = 7.0,
    reliable: bool = True,
) -> RefrigerantInput:
    """Build a RefrigerantInput producing a given superheat (Tg - Te = sh)."""
    return RefrigerantInput(
        operation_mode=mode,
        compressor_frequency=freq,
        gas_temp=None if te is None else te + sh,
        evaporator_temp=te,
        outdoor_expansion_valve=evo,
        outdoor_temp=outdoor,
        data_reliable=reliable,
    )


def _new_monitor() -> RefrigerantMonitor:
    """Return a fresh monitor backed by a bounded in-memory storage."""
    return RefrigerantMonitor(InMemoryStorage(max_len=HISTORY_DAYS))


def _feed_days(
    monitor: RefrigerantMonitor,
    specs: list[dict],
    *,
    start: date = date(2026, 1, 1),
    samples: int = MIN_SAMPLES_PER_DAY,
) -> None:
    """Feed one day per spec, then flush the last day.

    Each spec is a dict of signal params (sh, te, evo, outdoor). A day-boundary
    update flushes the previous day; a trailing off-mode update flushes the last.
    """
    for i, spec in enumerate(specs):
        day = start + timedelta(days=i)
        ts = datetime(day.year, day.month, day.day, 12, 0, 0)
        for _ in range(samples):
            monitor.update(_make_input(**spec), timestamp=ts)
    flush_day = start + timedelta(days=len(specs))
    flush_ts = datetime(flush_day.year, flush_day.month, flush_day.day, 0, 0, 0)
    # off-mode update: no new sample, but triggers the flush of the last real day.
    monitor.update(_make_input(mode="off"), timestamp=flush_ts)


def _baseline_specs(days: int = BASELINE_DAYS) -> list[dict]:
    """Return `days` identical steady-state day specs for a clean baseline."""
    return [{"sh": 5.0, "te": -5.0, "evo": 40.0, "outdoor": 7.0} for _ in range(days)]


class TestSamplingGate:
    """A sample is only recorded when every gate condition holds."""

    @pytest.mark.parametrize(
        "override",
        [
            {"mode": "cooling"},
            {"mode": "dhw"},
            {"mode": None},
            {"reliable": False},
            {"freq": 5.0},  # below MIN_FREQUENCY
            {"freq": 200.0},  # above MAX_FREQUENCY
            {"freq": None},
            {"te": None},  # missing Te -> superheat undefined
            {"evo": 65535.0},  # 0xFFFF sentinel, out of plausible range
            {"sh": 100.0},  # implausible superheat
            {"outdoor": 80.0},  # implausible outdoor temp
        ],
    )
    def test_rejected_samples_do_not_accumulate(self, override: dict) -> None:
        """Samples failing any gate condition are dropped."""
        monitor = _new_monitor()
        ts = datetime(2026, 1, 1, 12, 0, 0)
        for _ in range(MIN_SAMPLES_PER_DAY):
            monitor.update(_make_input(**override), timestamp=ts)
        assert monitor.get_status().today_samples == 0

    def test_valid_samples_accumulate(self) -> None:
        """Qualifying samples are counted in the current day's buffer."""
        monitor = _new_monitor()
        ts = datetime(2026, 1, 1, 12, 0, 0)
        for _ in range(MIN_SAMPLES_PER_DAY):
            monitor.update(_make_input(), timestamp=ts)
        assert monitor.get_status().today_samples == MIN_SAMPLES_PER_DAY


class TestDailyAggregation:
    """Days below the sample threshold are discarded, not aggregated."""

    def test_sparse_day_is_not_valid(self) -> None:
        """A day with too few samples does not become a valid aggregate."""
        monitor = _new_monitor()
        _feed_days(
            monitor,
            [{"sh": 5.0, "te": -5.0, "evo": 40.0, "outdoor": 7.0}],
            samples=MIN_SAMPLES_PER_DAY - 1,
        )
        assert monitor.get_status().valid_days == 0

    def test_full_day_becomes_valid(self) -> None:
        """A day meeting the sample threshold yields one valid aggregate."""
        monitor = _new_monitor()
        _feed_days(monitor, _baseline_specs(1))
        assert monitor.get_status().valid_days == 1


class TestBaselineAndClassification:
    """Warm-up, then verdicts against the frozen baseline."""

    def test_learning_until_baseline(self) -> None:
        """Before enough baseline days, the status is `learning`."""
        monitor = _new_monitor()
        _feed_days(monitor, _baseline_specs(BASELINE_DAYS - 1))
        status = monitor.get_status()
        assert status.status == STATUS_LEARNING
        assert status.baseline is None

    def test_ok_after_baseline_without_drift(self) -> None:
        """A stable circuit reads `ok` once the baseline is frozen."""
        monitor = _new_monitor()
        _feed_days(monitor, _baseline_specs(BASELINE_DAYS))
        status = monitor.get_status()
        assert status.baseline is not None
        assert status.status == STATUS_OK

    def test_watch_on_superheat_only_drift(self) -> None:
        """Superheat drift alone escalates to `watch`, not `alert`."""
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)
        # 7 recent days: superheat +4 K, EVO unchanged -> watch, not alert.
        specs += [
            {"sh": 9.0, "te": -5.0, "evo": 40.0, "outdoor": 7.0} for _ in range(7)
        ]
        _feed_days(monitor, specs)
        status = monitor.get_status()
        assert status.status == STATUS_WATCH
        assert status.superheat_delta == pytest.approx(4.0)

    def test_alert_on_leak_signature(self) -> None:
        """Joint superheat + temperature-matched EVO drift raises `alert`."""
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)
        # 7 recent days: superheat +6 K and EVO +20 % at matched outdoor temp.
        specs += [
            {"sh": 11.0, "te": -8.0, "evo": 60.0, "outdoor": 7.0} for _ in range(7)
        ]
        _feed_days(monitor, specs)
        status = monitor.get_status()
        assert status.status == STATUS_ALERT
        assert status.superheat_delta == pytest.approx(6.0)
        assert status.exv_delta == pytest.approx(20.0)

    def test_no_false_alert_on_cold_shift(self) -> None:
        """A colder-weather shift with stable superheat stays `ok`."""
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)
        # Colder weather: EVO opens and Te drops, but superheat is stable and the
        # outdoor temperature is outside the match band -> no alert, EVO not compared.
        specs += [
            {"sh": 5.0, "te": -12.0, "evo": 62.0, "outdoor": -1.0} for _ in range(7)
        ]
        _feed_days(monitor, specs)
        status = monitor.get_status()
        assert status.status == STATUS_OK
        assert status.exv_delta is None

    def test_superheat_drift_capped_at_watch_without_matched_evo(self) -> None:
        """Strong superheat drift cannot reach `alert` if EVO is not temp-matched."""
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)
        # Superheat rises strongly but EVO drift cannot be temperature-matched.
        specs += [
            {"sh": 12.0, "te": -12.0, "evo": 65.0, "outdoor": -2.0} for _ in range(7)
        ]
        _feed_days(monitor, specs)
        status = monitor.get_status()
        assert status.status == STATUS_WATCH
        assert status.exv_delta is None


class TestAlertStreak:
    """The alert streak drives the repair-issue escalation."""

    def test_streak_builds_on_sustained_alert(self) -> None:
        """The streak grows while the alert condition persists day after day."""
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)
        specs += [
            {"sh": 12.0, "te": -8.0, "evo": 65.0, "outdoor": 7.0} for _ in range(10)
        ]
        _feed_days(monitor, specs)
        status = monitor.get_status()
        assert status.status == STATUS_ALERT
        assert status.alert_streak >= refr.ALERT_PERSIST_DAYS

    def test_streak_resets_when_recovering(self) -> None:
        """The streak returns to zero once the readings recover."""
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)
        specs += [
            {"sh": 12.0, "te": -8.0, "evo": 65.0, "outdoor": 7.0} for _ in range(6)
        ]
        # Recovery: readings return to baseline for several days.
        specs += [
            {"sh": 5.0, "te": -5.0, "evo": 40.0, "outdoor": 7.0} for _ in range(7)
        ]
        _feed_days(monitor, specs)
        status = monitor.get_status()
        assert status.status == STATUS_OK
        assert status.alert_streak == 0


class TestPersistence:
    """Serialize/restore round-trip and reset."""

    def test_serialize_restore_round_trip(self) -> None:
        """Restoring a serialized snapshot reproduces the same verdict."""
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)
        specs += [
            {"sh": 11.0, "te": -8.0, "evo": 60.0, "outdoor": 7.0} for _ in range(7)
        ]
        _feed_days(monitor, specs)
        before = monitor.get_status()

        state = monitor.serialize()
        restored = _new_monitor()
        restored.restore(state)
        after = restored.get_status()

        assert after.status == before.status
        assert after.valid_days == before.valid_days
        assert after.superheat_delta == before.superheat_delta
        assert after.exv_delta == before.exv_delta
        # Alert streak and every baseline field must round-trip faithfully.
        assert before.alert_streak > 0
        assert after.alert_streak == before.alert_streak
        assert before.baseline is not None
        assert after.baseline is not None
        assert after.baseline.superheat == before.baseline.superheat
        assert after.baseline.evaporation_temp == before.baseline.evaporation_temp
        assert after.baseline.exv == before.baseline.exv
        assert after.baseline.outdoor_temp == before.baseline.outdoor_temp
        assert after.baseline.days == before.baseline.days

    @pytest.mark.parametrize(
        "payload",
        [
            # baseline missing a required key
            {"baseline": {"superheat": 5.0}, "alert_streak": 0, "aggregates": []},
            # aggregate item missing keys
            {"baseline": None, "aggregates": [{"day": "2026-01-01"}]},
            # invalid ISO date in an otherwise complete aggregate dict
            {
                "baseline": None,
                "aggregates": [
                    {
                        "day": "not-a-date",
                        "superheat": 5.0,
                        "evaporation_temp": -5.0,
                        "exv": 40.0,
                        "outdoor_temp": 7.0,
                        "sample_count": 30,
                    }
                ],
            },
            # non-numeric value in an otherwise complete aggregate dict
            {
                "baseline": None,
                "aggregates": [
                    {
                        "day": "2026-01-01",
                        "superheat": "high",
                        "evaporation_temp": -5.0,
                        "exv": 40.0,
                        "outdoor_temp": 7.0,
                        "sample_count": 30,
                    }
                ],
            },
            # non-dict aggregate item
            {"aggregates": ["bogus"]},
        ],
    )
    def test_restore_malformed_payload_raises_and_preserves_state(
        self, payload: dict
    ) -> None:
        """A malformed snapshot raises ValueError and mutates no state."""
        monitor = _new_monitor()
        _feed_days(monitor, _baseline_specs())
        before = monitor.serialize()

        with pytest.raises(ValueError):
            monitor.restore(payload)

        assert monitor.serialize() == before

    def test_restore_malformed_payload_on_fresh_monitor_stays_empty(self) -> None:
        """A malformed snapshot on a fresh monitor raises and leaves it empty."""
        monitor = _new_monitor()

        with pytest.raises(ValueError):
            monitor.restore({"baseline": {"superheat": 5.0}})

        status = monitor.get_status()
        assert status.status == STATUS_LEARNING
        assert status.valid_days == 0
        assert status.alert_streak == 0

    def test_reset_clears_state(self) -> None:
        """Resetting drops the baseline and all aggregates."""
        monitor = _new_monitor()
        _feed_days(monitor, _baseline_specs(BASELINE_DAYS))
        assert monitor.get_status().baseline is not None

        monitor.reset()
        status = monitor.get_status()
        assert status.status == STATUS_LEARNING
        assert status.valid_days == 0
        assert status.baseline is None


class TestThresholdBoundaries:
    """Exactly-at-threshold values pin the >= / <= comparisons."""

    def test_superheat_exactly_watch_threshold(self) -> None:
        """DSH exactly at SUPERHEAT_WATCH_K classifies as watch."""
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)
        specs += [
            {
                "sh": 5.0 + refr.SUPERHEAT_WATCH_K,
                "te": -5.0,
                "evo": 40.0,
                "outdoor": 7.0,
            }
            for _ in range(7)
        ]
        _feed_days(monitor, specs)
        assert monitor.get_status().status == STATUS_WATCH

    def test_exactly_alert_thresholds(self) -> None:
        """DSH and dEVO both exactly at their alert thresholds classify as alert."""
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)
        specs += [
            {
                "sh": 5.0 + refr.SUPERHEAT_ALERT_K,
                "te": -8.0,
                "evo": 40.0 + refr.EVO_ALERT_PCT,
                "outdoor": 7.0,
            }
            for _ in range(7)
        ]
        _feed_days(monitor, specs)
        assert monitor.get_status().status == STATUS_ALERT

    def test_evo_just_below_alert_stays_watch(self) -> None:
        """Superheat at the alert threshold but EVO just below stays watch."""
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)
        specs += [
            {
                "sh": 5.0 + refr.SUPERHEAT_ALERT_K,
                "te": -8.0,
                "evo": 40.0 + refr.EVO_ALERT_PCT - 1.0,
                "outdoor": 7.0,
            }
            for _ in range(7)
        ]
        _feed_days(monitor, specs)
        assert monitor.get_status().status == STATUS_WATCH

    def test_temp_match_inclusive_at_boundary(self) -> None:
        """An outdoor diff exactly at TEMP_MATCH_K still counts as matched."""
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)  # baseline outdoor = 7.0
        specs += [
            {
                "sh": 11.0,
                "te": -8.0,
                "evo": 60.0,
                "outdoor": 7.0 + refr.TEMP_MATCH_K,
            }
            for _ in range(7)
        ]
        _feed_days(monitor, specs)
        status = monitor.get_status()
        assert status.status == STATUS_ALERT
        assert status.exv_delta is not None

    @pytest.mark.parametrize("freq", [refr.MIN_FREQUENCY, refr.MAX_FREQUENCY])
    def test_frequency_band_edges_are_inclusive(self, freq: float) -> None:
        """A sample exactly at MIN/MAX_FREQUENCY qualifies (inclusive bounds)."""
        monitor = _new_monitor()
        ts = datetime(2026, 1, 1, 12, 0, 0)
        for _ in range(MIN_SAMPLES_PER_DAY):
            monitor.update(_make_input(freq=freq), timestamp=ts)
        assert monitor.get_status().today_samples == MIN_SAMPLES_PER_DAY


class TestExactAlertStreak:
    """Deterministic streak arithmetic."""

    def test_streak_equals_expected_after_seven_drift_days(self) -> None:
        """With EVAL_DAYS=7, 7 leak days after baseline give a streak of 4.

        The recent-window median crosses to the drifted value once >= 4 of the
        7 trailing days are drift days, so the last 4 daily flushes read alert.
        """
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)
        specs += [
            {"sh": 11.0, "te": -8.0, "evo": 60.0, "outdoor": 7.0} for _ in range(7)
        ]
        _feed_days(monitor, specs)
        assert monitor.get_status().alert_streak == 4


class TestStaleness:
    """Data-age annotation of a verdict frozen off heating season."""

    def test_frozen_alert_is_annotated_stale(self) -> None:
        """A sustained alert keeps its verdict and reports the data age."""
        monitor = _new_monitor()
        specs = _baseline_specs(BASELINE_DAYS)
        specs += [
            {"sh": 12.0, "te": -8.0, "evo": 65.0, "outdoor": 7.0} for _ in range(10)
        ]
        _feed_days(monitor, specs, start=date(2026, 1, 1))
        # Last real day is BASELINE_DAYS + 10 - 1 days after the start.
        last_day = date(2026, 1, 1) + timedelta(days=BASELINE_DAYS + 10 - 1)
        assert monitor.get_status().status == STATUS_ALERT

        # Months later, an off-mode poll advances the calendar without a sample.
        later = datetime(2026, 6, 1, 12, 0, 0)
        monitor.update(_make_input(mode="off"), timestamp=later)

        status = monitor.get_status()
        assert status.status == STATUS_ALERT
        assert status.alert_streak >= refr.ALERT_PERSIST_DAYS
        assert status.last_valid_day == last_day
        assert status.days_since_valid_data == (later.date() - last_day).days

    def test_fresh_monitor_has_no_staleness(self) -> None:
        """With no aggregates yet, both staleness fields are None."""
        status = _new_monitor().get_status()
        assert status.last_valid_day is None
        assert status.days_since_valid_data is None

    def test_days_since_none_after_restore_without_update(self) -> None:
        """Right after restore(), no current day is known, so age is None."""
        source = _new_monitor()
        _feed_days(source, _baseline_specs(BASELINE_DAYS), start=date(2026, 1, 1))
        restored = _new_monitor()
        restored.restore(source.serialize())

        status = restored.get_status()
        assert status.last_valid_day is not None
        assert status.days_since_valid_data is None

    def test_staleness_recomputed_after_restore_and_update(self) -> None:
        """A dated update() after restore() recomputes the data age."""
        source = _new_monitor()
        _feed_days(source, _baseline_specs(BASELINE_DAYS), start=date(2026, 1, 1))
        last_day = date(2026, 1, 1) + timedelta(days=BASELINE_DAYS - 1)

        restored = _new_monitor()
        restored.restore(source.serialize())

        later = datetime(2026, 5, 1, 12, 0, 0)
        restored.update(_make_input(mode="off"), timestamp=later)

        status = restored.get_status()
        assert status.last_valid_day == last_day
        assert status.days_since_valid_data == (later.date() - last_day).days


def test_multi_day_gap_adds_no_spurious_aggregate() -> None:
    """A multi-day offline gap produces no phantom day and does not corrupt state."""
    monitor = _new_monitor()
    _feed_days(monitor, _baseline_specs(BASELINE_DAYS), start=date(2026, 1, 1))
    assert monitor.get_status().valid_days == BASELINE_DAYS

    # Resume weeks later: the gap must add no aggregate, only the 7 real days.
    specs = [{"sh": 11.0, "te": -8.0, "evo": 60.0, "outdoor": 7.0} for _ in range(7)]
    _feed_days(monitor, specs, start=date(2026, 2, 1))

    status = monitor.get_status()
    assert status.valid_days == BASELINE_DAYS + 7
    assert status.status == STATUS_ALERT


def test_history_window_is_bounded() -> None:
    """The daily-aggregate storage never grows past HISTORY_DAYS."""
    monitor = _new_monitor()
    _feed_days(monitor, _baseline_specs(HISTORY_DAYS + 10))
    assert monitor.get_status().valid_days == HISTORY_DAYS
