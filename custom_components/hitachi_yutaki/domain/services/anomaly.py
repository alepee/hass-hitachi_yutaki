"""Anomaly baseline service for refrigerant circuit monitoring.

Maintains a per-installation rolling buffer of refrigerant-circuit signal
samples and gates 'ok' state behind BOTH a minimum calendar duration AND a
minimum sample count (dual warm-up gate).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ..ports.storage import Storage

ANOMALY_MIN_SAMPLES: int = 30
ANOMALY_MIN_DURATION_SECONDS: float = 3600.0


@dataclass
class RefrigerantSample:
    """A single refrigerant-circuit signal sample."""

    timestamp: float
    tg_gas: float | None
    ti_liquid: float | None
    td_discharge: float | None
    te_evaporator: float | None
    frequency: float | None
    current: float | None


class AnomalyBaselineService:
    """Per-installation rolling baseline with dual warm-up gate.

    Stays 'warming_up' until BOTH duration AND sample-count thresholds are met.
    Once both thresholds are satisfied, reports 'ok'.
    """

    def __init__(
        self,
        storage: Storage[RefrigerantSample],
        min_samples: int = ANOMALY_MIN_SAMPLES,
        min_duration_seconds: float = ANOMALY_MIN_DURATION_SECONDS,
    ) -> None:
        """Initialise the service.

        Args:
            storage: InMemoryStorage-backed rolling buffer.
            min_samples: Minimum number of samples required before 'ok'.
            min_duration_seconds: Minimum elapsed wall-clock time before 'ok'.

        """
        self._storage = storage
        self._min_samples = min_samples
        self._min_duration_seconds = min_duration_seconds
        self._start_time: float | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, sample: RefrigerantSample) -> None:
        """Record a new sample.

        Sets the start time on the very first call, then appends to the
        rolling buffer.  Old entries that fall outside the rolling window
        are pruned so the buffer does not grow unboundedly when used with
        an unlimited-size storage.

        Args:
            sample: The new refrigerant circuit sample.

        """
        if self._start_time is None:
            self._start_time = sample.timestamp

        self._storage.append(sample)

        # Prune entries that are older than the rolling window.  This is
        # a no-op when the storage has a fixed max_len (InMemoryStorage
        # handles eviction automatically via the deque maxlen), but it
        # keeps things correct for unlimited-size storage too.
        cutoff = sample.timestamp - self._min_duration_seconds * 2
        while len(self._storage) > 0:
            oldest = self._storage.get_all()[0]
            if oldest.timestamp < cutoff:
                self._storage.popleft()
            else:
                break

    @property
    def state(self) -> str:
        """Return 'ok' when BOTH thresholds are satisfied, else 'warming_up'."""
        if self._start_time is None:
            return "warming_up"
        duration_ok = (time.monotonic() - self._start_time) >= self._min_duration_seconds
        samples_ok = len(self._storage) >= self._min_samples
        if duration_ok and samples_ok:
            return "ok"
        return "warming_up"

    @property
    def elapsed_seconds(self) -> float:
        """Return elapsed seconds since the first sample, or 0.0."""
        if self._start_time is None:
            return 0.0
        return time.monotonic() - self._start_time

    @property
    def sample_count(self) -> int:
        """Return the current number of samples in the buffer."""
        return len(self._storage)

    @property
    def min_samples(self) -> int:
        """Return the minimum sample count threshold."""
        return self._min_samples

    @property
    def min_duration_seconds(self) -> float:
        """Return the minimum duration threshold in seconds."""
        return self._min_duration_seconds
