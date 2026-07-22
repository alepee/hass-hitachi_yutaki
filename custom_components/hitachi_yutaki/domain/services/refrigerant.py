"""Refrigerant-circuit anomaly detection service.

Detects a slow refrigerant charge loss between two mandatory F-Gas leak-tightness
inspections. It **complements** and does not replace the legal inspection.

Pure business logic, isolated from Home Assistant. Mirrors the COP service:
optional ``timestamp`` for replay/tests and ``time()`` for the sample-interval
throttle. See ``docs/reference/refrigerant-monitoring.md`` for the rationale.

Physical basis: a slow undercharge raises suction superheat ``SH = Tg - Te`` and
drives the expansion valve (EVO) further open to compensate, while the
evaporating temperature ``Te`` drifts down. Superheat is a *regulated* quantity,
so it is robust to seasonal variation; EVO and Te are not, and are compared only
at equivalent outdoor temperature (EVO) or reported for information (Te).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from statistics import median
from time import time
from typing import Any

from ..models.operation import MODE_HEATING
from ..models.refrigerant import (
    DailyAggregate,
    RefrigerantBaseline,
    RefrigerantInput,
    RefrigerantStatus,
)
from ..ports.storage import Storage

# Sampling gate
SAMPLE_MIN_INTERVAL_S = 60  # at most one sample per minute (like COP)
MIN_FREQUENCY = 20.0  # Hz — skip idle and very-low-load startup noise
MAX_FREQUENCY = 150.0  # Hz — keep load roughly comparable

# Plausibility bounds (a sample outside any bound is discarded)
SUPERHEAT_MIN_K = -10.0
SUPERHEAT_MAX_K = 40.0
EVO_MIN_PCT = 0.0
EVO_MAX_PCT = 100.0  # datasheet range; also guards EVO's 0xFFFF (=65535) case
EVAP_MIN_C = -60.0
EVAP_MAX_C = 40.0
OUTDOOR_MIN_C = -40.0
OUTDOOR_MAX_C = 40.0

# Daily aggregation
MIN_SAMPLES_PER_DAY = 30  # ~30 min of qualifying heating for a "valid" day
HISTORY_DAYS = 45  # rolling window of daily aggregates

# Baseline / evaluation
BASELINE_DAYS = 14  # valid days needed to freeze the baseline
EVAL_DAYS = 7  # trailing valid days forming the recent window
MIN_EVAL_DAYS = 3  # minimum recent days before a verdict beyond `ok`
TEMP_MATCH_K = 4.0  # outdoor-temperature band for the EVO comparison

# Thresholds (heuristic, conservative)
SUPERHEAT_WATCH_K = 3.0
SUPERHEAT_ALERT_K = 5.0
EVO_ALERT_PCT = 15.0

# Alert persistence before a repair issue is raised
ALERT_PERSIST_DAYS = 3

# Status values (also the ENUM options of the diagnostic sensor)
STATUS_LEARNING = "learning"
STATUS_OK = "ok"
STATUS_WATCH = "watch"
STATUS_ALERT = "alert"


class RefrigerantMonitor:
    """Accumulates daily refrigerant statistics and detects a slow charge loss.

    The service is independent of Home Assistant and infrastructure concerns.
    Daily aggregates (one per day) are held in the injected ``Storage`` so weeks
    of history cost a handful of records; intra-day samples live in a transient
    in-memory buffer that is intentionally not persisted.
    """

    def __init__(self, storage: Storage[DailyAggregate]) -> None:
        """Initialize the monitor with a bounded daily-aggregate storage."""
        self._storage = storage
        self._baseline: RefrigerantBaseline | None = None
        self._alert_streak = 0

        # Transient intra-day buffers (volatile across restarts).
        self._current_day: date | None = None
        self._superheats: list[float] = []
        self._evos: list[float] = []
        self._evaps: list[float] = []
        self._outdoors: list[float] = []
        self._last_sample_time = 0.0

    def update(
        self, data: RefrigerantInput, *, timestamp: datetime | None = None
    ) -> bool:
        """Feed one poll of signals.

        Returns ``True`` when a daily aggregate was just flushed (a cue for the
        adapter to persist the serialized state).
        """
        now = timestamp or datetime.now()
        today = now.date()

        flushed = False
        if self._current_day is None:
            self._current_day = today
        elif today != self._current_day:
            flushed = self._flush_day()
            self._current_day = today

        if not self._should_sample(data):
            return flushed

        # Throttle: at most one sample per interval.
        current = time()
        if current - self._last_sample_time < SAMPLE_MIN_INTERVAL_S:
            return flushed

        superheat = data.gas_temp - data.evaporator_temp  # type: ignore[operator]
        if not (SUPERHEAT_MIN_K <= superheat <= SUPERHEAT_MAX_K):
            return flushed
        if not (EVO_MIN_PCT <= data.outdoor_expansion_valve <= EVO_MAX_PCT):  # type: ignore[operator]
            return flushed
        if not (EVAP_MIN_C <= data.evaporator_temp <= EVAP_MAX_C):  # type: ignore[operator]
            return flushed
        if not (OUTDOOR_MIN_C <= data.outdoor_temp <= OUTDOOR_MAX_C):  # type: ignore[operator]
            return flushed

        self._last_sample_time = current
        self._superheats.append(superheat)
        self._evos.append(data.outdoor_expansion_valve)  # type: ignore[arg-type]
        self._evaps.append(data.evaporator_temp)  # type: ignore[arg-type]
        self._outdoors.append(data.outdoor_temp)  # type: ignore[arg-type]
        return flushed

    def get_status(self) -> RefrigerantStatus:
        """Return the current detector verdict."""
        return self._evaluate()

    def serialize(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the persistent state."""
        return {
            "baseline": (
                None
                if self._baseline is None
                else {
                    "superheat": self._baseline.superheat,
                    "evaporation_temp": self._baseline.evaporation_temp,
                    "exv": self._baseline.exv,
                    "outdoor_temp": self._baseline.outdoor_temp,
                    "days": self._baseline.days,
                }
            ),
            "alert_streak": self._alert_streak,
            "aggregates": [
                {
                    "day": aggregate.day.isoformat(),
                    "superheat": aggregate.superheat,
                    "evaporation_temp": aggregate.evaporation_temp,
                    "exv": aggregate.exv,
                    "outdoor_temp": aggregate.outdoor_temp,
                    "sample_count": aggregate.sample_count,
                }
                for aggregate in self._storage.get_all()
            ],
        }

    def restore(self, state: dict[str, Any] | None) -> None:
        """Restore persistent state from a serialized snapshot."""
        if not state:
            return

        # Full reset first, so restoring onto any monitor is idempotent.
        self._baseline = None
        self._current_day = None
        self._reset_day_buffers()
        while len(self._storage):
            self._storage.popleft()

        baseline = state.get("baseline")
        if baseline:
            self._baseline = RefrigerantBaseline(
                superheat=baseline["superheat"],
                evaporation_temp=baseline["evaporation_temp"],
                exv=baseline["exv"],
                outdoor_temp=baseline["outdoor_temp"],
                days=baseline.get("days", BASELINE_DAYS),
            )
        self._alert_streak = state.get("alert_streak", 0)

        for item in state.get("aggregates", []):
            self._storage.append(
                DailyAggregate(
                    day=date.fromisoformat(item["day"]),
                    superheat=item["superheat"],
                    evaporation_temp=item["evaporation_temp"],
                    exv=item["exv"],
                    outdoor_temp=item["outdoor_temp"],
                    sample_count=item["sample_count"],
                )
            )

    def reset(self) -> None:
        """Clear all state (used after a refrigerant top-up or EXV service)."""
        self._baseline = None
        self._alert_streak = 0
        self._current_day = None
        self._reset_day_buffers()
        while len(self._storage):
            self._storage.popleft()

    def _flush_day(self) -> bool:
        """Aggregate the finished day, freeze the baseline, update the streak."""
        count = len(self._superheats)
        added = False
        if count >= MIN_SAMPLES_PER_DAY and self._current_day is not None:
            self._storage.append(
                DailyAggregate(
                    day=self._current_day,
                    superheat=median(self._superheats),
                    evaporation_temp=median(self._evaps),
                    exv=median(self._evos),
                    outdoor_temp=median(self._outdoors),
                    sample_count=count,
                )
            )
            added = True

            if self._baseline is None:
                aggregates = self._storage.get_all()
                if len(aggregates) >= BASELINE_DAYS:
                    base = aggregates[:BASELINE_DAYS]
                    self._baseline = RefrigerantBaseline(
                        superheat=median(a.superheat for a in base),
                        evaporation_temp=median(a.evaporation_temp for a in base),
                        exv=median(a.exv for a in base),
                        outdoor_temp=median(a.outdoor_temp for a in base),
                        days=BASELINE_DAYS,
                    )

            if self._evaluate().status == STATUS_ALERT:
                self._alert_streak += 1
            else:
                self._alert_streak = 0

        self._reset_day_buffers()
        return added

    def _evaluate(self) -> RefrigerantStatus:
        """Classify the circuit from the frozen baseline and the recent window."""
        aggregates = self._storage.get_all()
        valid_days = len(aggregates)
        today_samples = len(self._superheats)

        if self._baseline is None:
            return RefrigerantStatus(
                status=STATUS_LEARNING,
                superheat_delta=None,
                exv_delta=None,
                evaporation_temp_delta=None,
                baseline=None,
                valid_days=valid_days,
                today_samples=today_samples,
                alert_streak=self._alert_streak,
            )

        recent = aggregates[-EVAL_DAYS:]
        if len(recent) < MIN_EVAL_DAYS:
            return RefrigerantStatus(
                status=STATUS_OK,
                superheat_delta=None,
                exv_delta=None,
                evaporation_temp_delta=None,
                baseline=self._baseline,
                valid_days=valid_days,
                today_samples=today_samples,
                alert_streak=self._alert_streak,
            )

        delta_superheat = median(a.superheat for a in recent) - self._baseline.superheat
        delta_evap = (
            median(a.evaporation_temp for a in recent) - self._baseline.evaporation_temp
        )

        # EVO is compared like-for-like on outdoor temperature.
        matched = [
            a
            for a in recent
            if abs(a.outdoor_temp - self._baseline.outdoor_temp) <= TEMP_MATCH_K
        ]
        delta_exv: float | None = None
        if len(matched) >= MIN_EVAL_DAYS:
            delta_exv = median(a.exv for a in matched) - self._baseline.exv

        if (
            delta_superheat >= SUPERHEAT_ALERT_K
            and delta_exv is not None
            and delta_exv >= EVO_ALERT_PCT
        ):
            status = STATUS_ALERT
        elif delta_superheat >= SUPERHEAT_WATCH_K:
            status = STATUS_WATCH
        else:
            status = STATUS_OK

        return RefrigerantStatus(
            status=status,
            superheat_delta=round(delta_superheat, 2),
            exv_delta=None if delta_exv is None else round(delta_exv, 2),
            evaporation_temp_delta=round(delta_evap, 2),
            baseline=self._baseline,
            valid_days=valid_days,
            today_samples=today_samples,
            alert_streak=self._alert_streak,
        )

    def _should_sample(self, data: RefrigerantInput) -> bool:
        """Return whether the current poll qualifies for sampling."""
        if not data.data_reliable:
            return False
        if data.operation_mode != MODE_HEATING:
            return False
        frequency = data.compressor_frequency
        if frequency is None or not (MIN_FREQUENCY <= frequency <= MAX_FREQUENCY):
            return False
        return not (
            data.gas_temp is None
            or data.evaporator_temp is None
            or data.outdoor_expansion_valve is None
            or data.outdoor_temp is None
        )

    def _reset_day_buffers(self) -> None:
        """Clear the transient intra-day sample buffers."""
        self._superheats = []
        self._evos = []
        self._evaps = []
        self._outdoors = []

    def preload_aggregates(self, aggregates: Iterable[DailyAggregate]) -> None:
        """Load historical daily aggregates (used by tests / rehydration)."""
        for aggregate in aggregates:
            self._storage.append(aggregate)
