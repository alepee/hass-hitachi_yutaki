"""COP (Coefficient of Performance) calculation logic."""

from datetime import datetime, timedelta
from typing import NamedTuple

from .storage import AbstractStorage

# Configuration constants for COP calculation
COP_MEASUREMENTS_HISTORY_SIZE = 100
COP_MEASUREMENTS_INTERVAL = 60  # seconds
COP_MEASUREMENTS_PERIOD = timedelta(minutes=30)
COP_MIN_MEASUREMENTS = 5
COP_MIN_TIME_SPAN = 5  # minutes
COP_OPTIMAL_MEASUREMENTS = 15
COP_OPTIMAL_TIME_SPAN = 15  # minutes


class PowerMeasurement(NamedTuple):
    """Class to store a power measurement with its timestamp."""

    timestamp: datetime
    thermal_power: float
    electrical_power: float


class EnergyAccumulator:
    """Class to accumulate energy over time for COP calculation."""

    def __init__(
        self, storage: AbstractStorage[PowerMeasurement], period: timedelta
    ) -> None:
        """Initialize the accumulator."""
        self._storage = storage
        self.period = period

    @property
    def measurements(self) -> list[PowerMeasurement]:
        """Return all measurements from storage."""
        return self._storage.get_all()

    def add_measurement(self, thermal_power: float, electrical_power: float) -> None:
        """Add a power measurement to the accumulator."""
        current_time = datetime.now()
        self._storage.append(
            PowerMeasurement(current_time, thermal_power, electrical_power)
        )

        # Remove measurements older than the period
        measurements = self._storage.get_all()
        cutoff_time = current_time - self.period
        while measurements and measurements[0].timestamp < cutoff_time:
            self._storage.popleft()
            measurements = self._storage.get_all()

    def get_cop(self) -> float | None:
        """Calculate COP from accumulated energy."""
        measurements = self._storage.get_all()
        if not measurements:
            return None

        # Calculate total energy by integrating power over time
        thermal_energy = 0.0
        electrical_energy = 0.0

        for i in range(len(measurements) - 1):
            interval_in_seconds = (
                measurements[i + 1].timestamp - measurements[i].timestamp
            ).total_seconds()
            interval_in_hours = interval_in_seconds / 3600  # hours
            avg_thermal_power = (
                measurements[i].thermal_power + measurements[i + 1].thermal_power
            ) / 2
            avg_electrical_power = (
                measurements[i].electrical_power + measurements[i + 1].electrical_power
            ) / 2

            thermal_energy += avg_thermal_power * interval_in_hours
            electrical_energy += avg_electrical_power * interval_in_hours

        if electrical_energy <= 0:
            return None

        # Validate energy values (reasonable ranges for residential heat pump)
        if thermal_energy < 0.01 or thermal_energy > 100.0:
            return None

        if electrical_energy < 0.01 or electrical_energy > 50.0:
            return None

        cop_value = thermal_energy / electrical_energy

        # Validate final COP value (reasonable range for heat pump)
        if cop_value < 0.5 or cop_value > 8.0:
            return None

        return cop_value
