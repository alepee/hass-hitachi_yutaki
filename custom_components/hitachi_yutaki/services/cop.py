"""COP (Coefficient of Performance) calculation logic.

This module is isolated from Home Assistant to facilitate testing.
All data must be provided as input parameters.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import time
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


@dataclass
class COPInput:
    """Input data required for COP calculation."""

    water_inlet_temp: float | None
    water_outlet_temp: float | None
    water_flow: float | None
    compressor_current: float | None
    compressor_frequency: float | None
    secondary_compressor_current: float | None = None
    secondary_compressor_frequency: float | None = None


@dataclass
class COPQuality:
    """Quality assessment of COP measurement."""

    quality: str  # "no_data", "insufficient_data", "preliminary", "optimal"
    measurements: int
    time_span_minutes: float


# Type aliases for calculator functions
ThermalPowerCalculator = Callable[[float, float, float], float]
ElectricalPowerCalculator = Callable[[float], float]


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

    def get_quality(self) -> COPQuality:
        """Assess the quality of the COP measurement."""
        measurements = self.measurements
        if not measurements:
            return COPQuality(quality="no_data", measurements=0, time_span_minutes=0.0)

        # Calculate time span of measurements
        time_span = (
            measurements[-1].timestamp - measurements[0].timestamp
        ).total_seconds() / 60  # minutes
        num_measurements = len(measurements)

        if num_measurements < COP_MIN_MEASUREMENTS or time_span < COP_MIN_TIME_SPAN:
            quality = "insufficient_data"
        elif (
            num_measurements < COP_OPTIMAL_MEASUREMENTS
            or time_span < COP_OPTIMAL_TIME_SPAN
        ):
            quality = "preliminary"
        else:
            quality = "optimal"

        return COPQuality(
            quality=quality,
            measurements=num_measurements,
            time_span_minutes=round(time_span, 1),
        )


class COPSensor:
    """Orchestrates COP calculation with all required logic.

    This class is independent of Home Assistant and can be easily tested.
    """

    def __init__(
        self,
        accumulator: EnergyAccumulator,
        thermal_calculator: ThermalPowerCalculator,
        electrical_calculator: ElectricalPowerCalculator,
    ) -> None:
        """Initialize the COP sensor."""
        self._accumulator = accumulator
        self._thermal_calculator = thermal_calculator
        self._electrical_calculator = electrical_calculator
        self._last_measurement_time = 0.0

    def update(self, data: COPInput) -> None:
        """Update COP calculation with new data.

        This method should be called periodically with fresh sensor data.
        It will determine if a new measurement should be taken based on timing.
        """
        # Check if compressor is running
        if not self._is_compressor_running(data):
            return

        # Check if enough time has passed since last measurement
        current_time = time()
        if current_time - self._last_measurement_time < COP_MEASUREMENTS_INTERVAL:
            return

        self._last_measurement_time = current_time

        # Validate input data
        if any(
            x is None
            for x in [
                data.water_inlet_temp,
                data.water_outlet_temp,
                data.water_flow,
                data.compressor_current,
            ]
        ):
            return

        # Calculate thermal power
        thermal_power = self._thermal_calculator(
            data.water_inlet_temp,  # type: ignore
            data.water_outlet_temp,  # type: ignore
            data.water_flow,  # type: ignore
        )

        # Calculate electrical power from primary compressor
        electrical_power = self._electrical_calculator(
            data.compressor_current  # type: ignore
        )

        # Add secondary compressor power if available and running
        if (
            data.secondary_compressor_current is not None
            and data.secondary_compressor_frequency is not None
            and data.secondary_compressor_frequency > 0
        ):
            additional_power = self._electrical_calculator(
                data.secondary_compressor_current
            )
            if additional_power > 0:
                electrical_power += additional_power

        # Store measurement if valid
        if thermal_power > 0 and electrical_power > 0:
            self._accumulator.add_measurement(thermal_power, electrical_power)

    def get_value(self) -> float | None:
        """Get current COP value."""
        cop = self._accumulator.get_cop()
        return round(cop, 2) if cop is not None else None

    def get_quality(self) -> COPQuality:
        """Get quality assessment of the COP measurement."""
        return self._accumulator.get_quality()

    @staticmethod
    def _is_compressor_running(data: COPInput) -> bool:
        """Check if compressor is running based on frequency."""
        return data.compressor_frequency is not None and data.compressor_frequency > 0
