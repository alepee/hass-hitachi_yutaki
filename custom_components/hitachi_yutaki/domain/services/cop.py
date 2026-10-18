"""COP (Coefficient of Performance) calculation service.

Pure business logic isolated from infrastructure concerns.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

from ..models.clock import (
    Timeline,
    civil_time,
    elapsed_time,
    validate_timestamp_awareness,
)
from ..models.cop import COPInput, COPQuality, PowerMeasurement
from ..ports.calculators import ElectricalPowerCalculator, ThermalPowerCalculator
from ..ports.clock import Clock
from ..ports.storage import Storage

# Configuration constants
COP_MEASUREMENTS_HISTORY_SIZE = 100
COP_MEASUREMENTS_INTERVAL = 60  # seconds
COP_MEASUREMENTS_PERIOD = timedelta(minutes=30)
COP_MIN_MEASUREMENTS = 5
COP_MIN_TIME_SPAN = 5  # minutes
COP_OPTIMAL_MEASUREMENTS = 15
COP_OPTIMAL_TIME_SPAN = 15  # minutes


class EnergyAccumulator:
    """Accumulates energy measurements over time for COP calculation."""

    def __init__(
        self,
        storage: Storage[PowerMeasurement],
        period: timedelta,
        *,
        clock: Clock | None = None,
    ) -> None:
        """Initialize the accumulator.

        Args:
            clock: Injected time source for live measurements.
            storage: Storage implementation for measurements
            period: Time period to keep measurements

        """
        self._clock = clock
        self._storage = storage
        self.period = period

    @property
    def measurements(self) -> list[PowerMeasurement]:
        """Return all measurements from storage."""
        return self._storage.get_all()

    def add_measurement(
        self,
        thermal_power: float,
        electrical_power: float,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        """Add a power measurement to the accumulator."""
        current_time = civil_time(self._clock, timestamp)
        validate_timestamp_awareness(
            [current_time, *(item.timestamp for item in self._storage.get_all())]
        )
        self._storage.append(
            PowerMeasurement(current_time, thermal_power, electrical_power)
        )
        self._prune_old_measurements(current_time)

    def bulk_load(self, measurements: Iterable[PowerMeasurement]) -> None:
        """Load multiple historical measurements."""
        incoming = list(measurements)
        validate_timestamp_awareness(
            item.timestamp for item in [*self._storage.get_all(), *incoming]
        )
        last_timestamp: datetime | None = None
        for measurement in sorted(incoming, key=lambda item: item.timestamp):
            self._storage.append(measurement)
            last_timestamp = measurement.timestamp

        if last_timestamp is not None:
            self._prune_old_measurements(last_timestamp)

    def get_cop(self) -> float | None:
        """Calculate COP from accumulated energy using trapezoidal integration."""
        measurements = self._storage.get_all()
        if not measurements:
            return None

        # Sort measurements by timestamp to ensure correct integration
        measurements = sorted(measurements, key=lambda m: m.timestamp)

        # Calculate total energy by integrating power over time
        thermal_energy = 0.0
        electrical_energy = 0.0

        for i in range(len(measurements) - 1):
            interval_in_seconds = (
                measurements[i + 1].timestamp - measurements[i].timestamp
            ).total_seconds()
            interval_in_hours = interval_in_seconds / 3600
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

        # Sort measurements by timestamp to ensure correct time span calculation
        sorted_measurements = sorted(measurements, key=lambda m: m.timestamp)

        # Calculate time span of measurements
        time_span = (
            sorted_measurements[-1].timestamp - sorted_measurements[0].timestamp
        ).total_seconds() / 60
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

    def _prune_old_measurements(self, reference_time: datetime) -> None:
        """Remove measurements outside of the configured time period."""
        cutoff_time = reference_time - self.period
        measurements = self._storage.get_all()
        while measurements and measurements[0].timestamp < cutoff_time:
            self._storage.popleft()
            measurements = self._storage.get_all()


class COPService:
    """COP calculation service - orchestrates the calculation logic.

    This service is independent of Home Assistant and infrastructure concerns.
    """

    def __init__(
        self,
        accumulator: EnergyAccumulator,
        thermal_calculator: ThermalPowerCalculator,
        electrical_calculator: ElectricalPowerCalculator,
        *,
        expected_mode: str | None = None,
        clock: Clock | None = None,
    ) -> None:
        """Initialize the COP service.

        Args:
            clock: Injected time source for live measurements.
            accumulator: Energy accumulator for measurements
            thermal_calculator: Calculator for thermal power
            electrical_calculator: Calculator for electrical power
            expected_mode: Expected HVAC mode for this sensor (MODE_HEATING, MODE_COOLING,
                           MODE_DHW, MODE_POOL). If None, all modes are accepted.

        """
        self._clock = clock
        self._timeline = Timeline(clock)
        self._accumulator = accumulator
        self._thermal_calculator = thermal_calculator
        self._electrical_calculator = electrical_calculator
        self._expected_mode = expected_mode
        self._last_measurement_time: float | None = None

    def update(self, data: COPInput, *, timestamp: datetime | None = None) -> None:
        """Admit and accumulate a live or explicitly timestamped COP sample."""
        current_time = elapsed_time(self._clock, timestamp)
        if (
            self._last_measurement_time is not None
            and current_time - self._last_measurement_time < COP_MEASUREMENTS_INTERVAL
        ):
            return
        measurement = self.build_measurement(data, self._timeline.at(timestamp))
        if measurement is not None:
            self._last_measurement_time = current_time
            self._accumulator.add_measurement(
                measurement.thermal_power,
                measurement.electrical_power,
                timestamp=measurement.timestamp,
            )

    @property
    def expected_mode(self) -> str | None:
        """Return the explicit operation-mode filter shared with replay."""
        return self._expected_mode

    def build_measurement(
        self, data: COPInput, timestamp: datetime
    ) -> PowerMeasurement | None:
        """Apply this service's pure admission and calculators to a replay point."""
        return build_cop_measurement(
            data,
            timestamp,
            self._thermal_calculator,
            self._electrical_calculator,
            expected_mode=self._expected_mode,
        )

    def get_value(self) -> float | None:
        """Get current COP value rounded to 2 decimals."""
        cop = self._accumulator.get_cop()
        return round(cop, 2) if cop is not None else None

    def get_quality(self) -> COPQuality:
        """Get quality assessment of the COP measurement."""
        return self._accumulator.get_quality()

    def preload_measurements(self, measurements: Iterable[PowerMeasurement]) -> None:
        """Preload measurements (used during Recorder replay)."""
        self._accumulator.bulk_load(measurements)


def build_cop_measurement(
    data: COPInput,
    timestamp: datetime,
    thermal_calculator: ThermalPowerCalculator,
    electrical_calculator: ElectricalPowerCalculator,
    *,
    expected_mode: str | None = None,
) -> PowerMeasurement | None:
    """Pure admission and power calculation, identical for live and replay.

    A measured whole-unit power overrides current estimates, including zero
    current. Sum S80 currents before calling the fallback calculator once.
    """
    if data.compressor_frequency is None or data.compressor_frequency <= 0:
        return None
    if expected_mode is not None and data.operation_mode != expected_mode:
        return None
    inlet, outlet, flow = data.water_inlet_temp, data.water_outlet_temp, data.water_flow
    current = data.compressor_current
    if inlet is None or outlet is None or flow is None or current is None:
        return None
    thermal_power = thermal_calculator(inlet, outlet, flow)
    electrical_power = calculate_cop_electrical_power(data, electrical_calculator)
    if thermal_power <= 0 or electrical_power is None or electrical_power <= 0:
        return None
    return PowerMeasurement(timestamp, thermal_power, electrical_power)


def calculate_cop_electrical_power(
    data: COPInput, electrical_calculator: ElectricalPowerCalculator
) -> float | None:
    """Resolve whole-unit power once, summing active S80 currents for fallback."""
    if data.electrical_power is not None:
        return data.electrical_power
    current = data.compressor_current
    if current is None:
        return None
    if (
        data.secondary_compressor_current is not None
        and data.secondary_compressor_frequency is not None
        and data.secondary_compressor_frequency > 0
    ):
        current += data.secondary_compressor_current
    return electrical_calculator(current)
