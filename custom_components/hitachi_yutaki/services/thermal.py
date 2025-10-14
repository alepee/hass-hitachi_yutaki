"""Thermal power and energy calculation logic."""

from dataclasses import dataclass
from datetime import date, datetime
from time import time

# Constants for thermal calculations
WATER_FLOW_TO_KGS = 0.277778  # 1 m³/h = 1000 L/h = 1000 kg/h = 0.277778 kg/s
WATER_SPECIFIC_HEAT = 4.185  # kJ/kg·K


@dataclass
class ThermalPowerInput:
    """Input data for thermal power calculation."""

    water_inlet_temp: float
    water_outlet_temp: float
    water_flow: float


def calculate_thermal_power(data: ThermalPowerInput) -> float:
    """Calculate thermal power in kW from input data."""
    water_flow_kgs = data.water_flow * WATER_FLOW_TO_KGS
    delta_t = data.water_outlet_temp - data.water_inlet_temp
    thermal_power = abs(water_flow_kgs * WATER_SPECIFIC_HEAT * delta_t)
    return thermal_power


class ThermalEnergyAccumulator:
    """Class to accumulate thermal energy over time."""

    def __init__(self, initial_daily: float = 0.0, initial_total: float = 0.0) -> None:
        """Initialize the accumulator."""
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

    def update(self, thermal_power: float) -> None:
        """Update the energy accumulation with a new power measurement."""
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
