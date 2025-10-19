"""Thermal power and energy calculation service.

Pure business logic isolated from infrastructure concerns.
"""

from __future__ import annotations

from datetime import date, datetime
from time import time

from ..models.thermal import ThermalEnergyResult, ThermalPowerInput

# Constants for thermal calculations
WATER_FLOW_TO_KGS = 0.277778  # 1 m³/h = 1000 L/h = 1000 kg/h = 0.277778 kg/s
WATER_SPECIFIC_HEAT = 4.185  # kJ/kg·K


def calculate_thermal_power(data: ThermalPowerInput) -> float:
    """Calculate thermal power in kW from input data.

    Args:
        data: Input data containing temperatures and flow

    Returns:
        Thermal power in kW

    """
    water_flow_kgs = data.water_flow * WATER_FLOW_TO_KGS
    delta_t = data.water_outlet_temp - data.water_inlet_temp
    thermal_power = abs(water_flow_kgs * WATER_SPECIFIC_HEAT * delta_t)
    return thermal_power


class ThermalEnergyAccumulator:
    """Accumulates thermal energy over time for energy calculations."""

    def __init__(self, initial_daily: float = 0.0, initial_total: float = 0.0) -> None:
        """Initialize the accumulator.

        Args:
            initial_daily: Initial daily energy value
            initial_total: Initial total energy value

        """
        self._daily_energy = initial_daily
        self._total_energy = initial_total
        self._last_power = 0.0
        self._last_measurement_time = 0
        self._daily_start_time = 0
        self._last_reset = datetime.now().date()

    @property
    def daily_energy(self) -> float:
        """Return the accumulated daily energy in kWh."""
        return self._daily_energy

    @property
    def total_energy(self) -> float:
        """Return the accumulated total energy in kWh."""
        return self._total_energy

    @property
    def last_measurement_time(self) -> float:
        """Return the timestamp of the last measurement."""
        return self._last_measurement_time

    @property
    def daily_start_time(self) -> float:
        """Return the timestamp of the start of the daily accumulation."""
        return self._daily_start_time

    @property
    def last_reset_date(self) -> date:
        """Return the date of the last daily reset."""
        return self._last_reset

    def restore_daily_energy(self, energy: float) -> None:
        """Restore daily energy value (used after HA restart).

        Args:
            energy: Energy value to restore

        """
        self._daily_energy = energy

    def restore_total_energy(self, energy: float) -> None:
        """Restore total energy value (used after HA restart).

        Args:
            energy: Energy value to restore

        """
        self._total_energy = energy

    def update(self, thermal_power: float) -> None:
        """Update the energy accumulation with a new power measurement.

        Args:
            thermal_power: Current thermal power in kW

        """
        current_time = time()
        current_date = datetime.now().date()

        # Initialize daily start time if not set for the current day
        if self._daily_start_time == 0:
            self._daily_start_time = current_time

        # Reset daily counter at midnight
        if current_date != self._last_reset:
            self._daily_energy = 0.0
            self._last_reset = current_date
            self._daily_start_time = current_time  # Reset start time for new day

        # Calculate energy since last measurement
        if self._last_measurement_time > 0:
            time_diff_hours = (current_time - self._last_measurement_time) / 3600
            avg_power = (thermal_power + self._last_power) / 2
            energy = avg_power * time_diff_hours

            self._daily_energy += energy
            self._total_energy += energy

        self._last_power = thermal_power
        self._last_measurement_time = current_time


class ThermalPowerService:
    """Thermal power and energy calculation service.

    This service is independent of Home Assistant and can be easily tested.
    """

    def __init__(self, accumulator: ThermalEnergyAccumulator) -> None:
        """Initialize the thermal power service.

        Args:
            accumulator: Energy accumulator for calculations

        """
        self._accumulator = accumulator
        self._last_power = 0.0

    def update(
        self,
        water_inlet_temp: float | None,
        water_outlet_temp: float | None,
        water_flow: float | None,
        compressor_frequency: float | None,
    ) -> None:
        """Update thermal energy calculation with new data.

        Args:
            water_inlet_temp: Water inlet temperature in °C
            water_outlet_temp: Water outlet temperature in °C
            water_flow: Water flow rate in m³/h
            compressor_frequency: Compressor frequency in Hz (to check if running)

        """
        # Check if compressor is running
        if compressor_frequency is None or compressor_frequency <= 0:
            self._last_power = 0.0
            return

        # Validate input data
        if any(x is None for x in [water_inlet_temp, water_outlet_temp, water_flow]):
            self._last_power = 0.0
            return

        # Calculate thermal power
        thermal_power = calculate_thermal_power(
            ThermalPowerInput(
                water_inlet_temp,  # type: ignore
                water_outlet_temp,  # type: ignore
                water_flow,  # type: ignore
            )
        )

        # Update accumulator and store last power
        self._accumulator.update(thermal_power)
        self._last_power = thermal_power

    def get_power(self) -> float:
        """Get current thermal power in kW."""
        return round(self._last_power, 2) if self._last_power > 0 else 0

    def get_daily_energy(self) -> float:
        """Get daily thermal energy in kWh."""
        return round(self._accumulator.daily_energy, 2)

    def get_total_energy(self) -> float:
        """Get total thermal energy in kWh."""
        return round(self._accumulator.total_energy, 2)

    def restore_daily_energy(self, energy: float) -> None:
        """Restore daily energy state (used after HA restart).

        Args:
            energy: Energy value to restore

        """
        self._accumulator.restore_daily_energy(energy)

    def restore_total_energy(self, energy: float) -> None:
        """Restore total energy state (used after HA restart).

        Args:
            energy: Energy value to restore

        """
        self._accumulator.restore_total_energy(energy)

    def get_result(
        self, water_inlet_temp: float, water_outlet_temp: float, water_flow: float
    ) -> ThermalEnergyResult:
        """Get complete thermal energy result with all details.

        Args:
            water_inlet_temp: Water inlet temperature in °C
            water_outlet_temp: Water outlet temperature in °C
            water_flow: Water flow rate in m³/h

        Returns:
            Complete thermal energy result

        """
        delta_t = water_outlet_temp - water_inlet_temp
        last_update = (
            datetime.fromtimestamp(self._accumulator.last_measurement_time)
            if self._accumulator.last_measurement_time > 0
            else datetime.now()
        )
        daily_start = (
            datetime.fromtimestamp(self._accumulator.daily_start_time)
            if self._accumulator.daily_start_time > 0
            else datetime.now()
        )

        return ThermalEnergyResult(
            thermal_power=self._last_power,
            daily_energy=self._accumulator.daily_energy,
            total_energy=self._accumulator.total_energy,
            delta_t=delta_t,
            last_update=last_update,
            last_reset_date=self._accumulator.last_reset_date,
            daily_start_time=daily_start,
        )
