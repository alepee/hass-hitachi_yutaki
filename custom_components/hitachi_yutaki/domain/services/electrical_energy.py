"""Electrical energy and tariff accumulation, independent of infrastructure."""

from ..ports.clock import Clock

ENERGY_GAP_TOLERANCE_INTERVALS = 3
ENERGY_GAP_TOLERANCE_MIN_S = 30.0


class ElectricalEnergyAccumulator:
    """Integrate power with bounded outage gaps and optional per-poll tariffs."""

    def __init__(self, scan_interval: float, *, clock: Clock) -> None:
        """Configure the gap bound and inject elapsed time."""
        self._clock = clock
        self.max_gap = max(
            scan_interval * ENERGY_GAP_TOLERANCE_INTERVALS, ENERGY_GAP_TOLERANCE_MIN_S
        )
        self._last_time: float | None = None
        self.energy = 0.0
        self.cost = 0.0

    def update(self, power: float, price: float | None = None) -> None:
        """Accumulate kWh and cost; missing prices leave the cost unchanged."""
        now = self._clock.monotonic()
        elapsed = (
            0.0
            if self._last_time is None
            else max(0.0, min(now - self._last_time, self.max_gap))
        )
        delta = max(0.0, power) * elapsed / 3600
        self.energy += delta
        if price is not None and delta > 0:
            self.cost += round(delta * price, 6)
        self._last_time = now

    def restore_energy(self, value: float) -> None:
        """Restore persisted kWh without integrating downtime."""
        self.energy = value

    def restore_cost(self, value: float) -> None:
        """Restore persisted currency units without repricing past energy."""
        self.cost = value
