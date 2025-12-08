"""Thermal power and energy calculation service.

Pure business logic isolated from infrastructure concerns.
"""

from __future__ import annotations

from datetime import date, datetime
from time import time

from ..models.thermal import ThermalPowerInput

# Constants for thermal calculations
WATER_FLOW_TO_KGS = 0.277778  # 1 m³/h = 1000 L/h = 1000 kg/h = 0.277778 kg/s
WATER_SPECIFIC_HEAT = 4.185  # kJ/kg·K


def calculate_thermal_power(data: ThermalPowerInput) -> float:
    """Calculate signed thermal power in kW from input data.

    Positive values indicate heating (outlet > inlet).
    Negative values indicate cooling (outlet < inlet).

    Args:
        data: Input data containing temperatures and flow

    Returns:
        Signed thermal power in kW

    """
    water_flow_kgs = data.water_flow * WATER_FLOW_TO_KGS
    delta_t = data.water_outlet_temp - data.water_inlet_temp

    # Forcer ΔT à 0 si Tsortie - Tentrée < 0
    if delta_t < 0:
        delta_t = 0.0

    thermal_power = water_flow_kgs * WATER_SPECIFIC_HEAT * delta_t
    return thermal_power


def calculate_thermal_power_heating(data: ThermalPowerInput) -> float:
    """Calculate thermal power for heating mode.

    Returns positive power only when outlet > inlet (heating).
    Returns 0 when in cooling mode or invalid conditions.

    Args:
        data: Input data containing temperatures and flow

    Returns:
        Thermal power in kW (0 if cooling mode)

    """
    thermal_power = calculate_thermal_power(data)
    return max(0.0, thermal_power)


def calculate_thermal_power_cooling(data: ThermalPowerInput) -> float:
    """Calculate thermal power for cooling mode.

    Returns positive power only when outlet < inlet (cooling).
    Returns 0 when in heating mode or invalid conditions.

    Args:
        data: Input data containing temperatures and flow

    Returns:
        Thermal power in kW (0 if heating mode)

    """
    thermal_power = calculate_thermal_power(data)
    return max(0.0, -thermal_power)


class ThermalEnergyAccumulator:
    """Accumulates thermal energy over time for heating and cooling separately."""

    def __init__(
        self,
        initial_daily_heating: float = 0.0,
        initial_total_heating: float = 0.0,
        initial_daily_cooling: float = 0.0,
        initial_total_cooling: float = 0.0,
    ) -> None:
        """Initialize the accumulator.

        Args:
            initial_daily_heating: Initial daily heating energy value
            initial_total_heating: Initial total heating energy value
            initial_daily_cooling: Initial daily cooling energy value
            initial_total_cooling: Initial total cooling energy value

        """
        self._daily_heating_energy = initial_daily_heating
        self._total_heating_energy = initial_total_heating
        self._daily_cooling_energy = initial_daily_cooling
        self._total_cooling_energy = initial_total_cooling
        self._last_heating_power = 0.0
        self._last_cooling_power = 0.0
        self._last_measurement_time = 0
        self._daily_start_time = 0
        self._last_reset = datetime.now().date()

    @property
    def daily_heating_energy(self) -> float:
        """Return the accumulated daily heating energy in kWh."""
        return self._daily_heating_energy

    @property
    def total_heating_energy(self) -> float:
        """Return the accumulated total heating energy in kWh."""
        return self._total_heating_energy

    @property
    def daily_cooling_energy(self) -> float:
        """Return the accumulated daily cooling energy in kWh."""
        return self._daily_cooling_energy

    @property
    def total_cooling_energy(self) -> float:
        """Return the accumulated total cooling energy in kWh."""
        return self._total_cooling_energy

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

    def restore_daily_heating_energy(self, energy: float) -> None:
        """Restore daily heating energy value (used after HA restart).

        Args:
            energy: Energy value to restore

        """
        self._daily_heating_energy = energy

    def restore_total_heating_energy(self, energy: float) -> None:
        """Restore total heating energy value (used after HA restart).

        Args:
            energy: Energy value to restore

        """
        self._total_heating_energy = energy

    def restore_daily_cooling_energy(self, energy: float) -> None:
        """Restore daily cooling energy value (used after HA restart).

        Args:
            energy: Energy value to restore

        """
        self._daily_cooling_energy = energy

    def restore_total_cooling_energy(self, energy: float) -> None:
        """Restore total cooling energy value (used after HA restart).

        Args:
            energy: Energy value to restore

        """
        self._total_cooling_energy = energy

    def update(self, thermal_power: float, mode: str) -> None:
        """Update the energy accumulation with a new power measurement.

        Args:
            thermal_power: Current thermal power in kW
            mode: Operating mode ("heating" or "cooling")

        """
        current_time = time()
        current_date = datetime.now().date()

        # Initialize daily start time if not set for the current day
        if self._daily_start_time == 0:
            self._daily_start_time = current_time

        # Reset daily counters at midnight
        if current_date != self._last_reset:
            self._daily_heating_energy = 0.0
            self._daily_cooling_energy = 0.0
            self._last_reset = current_date
            self._daily_start_time = current_time  # Reset start time for new day

        # Calculate energy since last measurement
        if self._last_measurement_time > 0:
            time_diff_hours = (current_time - self._last_measurement_time) / 3600

            if mode == "heating":
                avg_power = (thermal_power + self._last_heating_power) / 2
                energy = avg_power * time_diff_hours
                self._daily_heating_energy += energy
                self._total_heating_energy += energy
                self._last_heating_power = thermal_power
                self._last_cooling_power = 0.0
            elif mode == "cooling":
                avg_power = (thermal_power + self._last_cooling_power) / 2
                energy = avg_power * time_diff_hours
                self._daily_cooling_energy += energy
                self._total_cooling_energy += energy
                self._last_cooling_power = thermal_power
                self._last_heating_power = 0.0
        # First measurement
        elif mode == "heating":
            self._last_heating_power = thermal_power
            self._last_cooling_power = 0.0
        elif mode == "cooling":
            self._last_cooling_power = thermal_power
            self._last_heating_power = 0.0

        self._last_measurement_time = current_time


class ThermalPowerService:
    """Thermal power and energy calculation service.

    This service is independent of Home Assistant and can be easily tested.
    Separates heating (ΔT > 0) and cooling (ΔT < 0) energy.
    """

    def __init__(self, accumulator: ThermalEnergyAccumulator) -> None:
        """Initialize the thermal power service.

        Args:
            accumulator: Energy accumulator for calculations

        """
        self._accumulator = accumulator
        self._last_heating_power = 0.0
        self._last_cooling_power = 0.0
        self._post_heating_lock = False
        self._last_mode: str | None = None

    def update(
        self,
        water_inlet_temp: float | None,
        water_outlet_temp: float | None,
        water_flow: float | None,
        compressor_frequency: float | None,
        is_defrosting: bool = False,
    ) -> None:
        """Update thermal energy calculation with new data.

        Args:
            water_inlet_temp: Water inlet temperature in °C
            water_outlet_temp: Water outlet temperature in °C
            water_flow: Water flow rate in m³/h
            compressor_frequency: Compressor frequency in Hz (to check if running)
            is_defrosting: True if heat pump is in defrost mode

        """
        # Ignore during defrost
        if is_defrosting:
            if self._last_mode is not None:
                self._accumulator.update(0.0, mode=self._last_mode)
            self._last_heating_power = 0.0
            self._last_cooling_power = 0.0
            return

        # Validate input data
        if any(x is None for x in [water_inlet_temp, water_outlet_temp, water_flow]):
            if self._last_mode is not None:
                self._accumulator.update(0.0, mode=self._last_mode)
            self._last_heating_power = 0.0
            self._last_cooling_power = 0.0
            return

        # Compresseur en marche ou non
        compressor_running = compressor_frequency is not None and compressor_frequency > 0

        # Si le compresseur redémarre, on sort du verrou post-chauffe
        if compressor_running:
            self._post_heating_lock = False

        # Calculate heating power (delta T > 0)
        heating_power = calculate_thermal_power_heating(
            ThermalPowerInput(
                water_inlet_temp,  # type: ignore
                water_outlet_temp,  # type: ignore
                water_flow,  # type: ignore
            )
        )

        # Calculate cooling power (delta T < 0)
        cooling_power = calculate_thermal_power_cooling(
            ThermalPowerInput(
                water_inlet_temp,  # type: ignore
                water_outlet_temp,  # type: ignore
                water_flow,  # type: ignore
            )
        )

        # Gestion de l'inertie et du verrou post-chauffe (chauffage uniquement)
        if not compressor_running:
            # Compresseur à l'arrêt : phase d'inertie possible
            if heating_power <= 0:
                # ΔT tombé à 0 avec compresseur arrêté → on verrouille
                self._post_heating_lock = True

            if self._post_heating_lock:
                # Verrou actif → on force la puissance de chauffe à 0
                heating_power = 0.0

        # Application des puissances effectives
        if heating_power > 0:
            # Période de chauffe active OU inertie (sans verrou)
            self._accumulator.update(heating_power, mode="heating")
            self._last_heating_power = heating_power
            self._last_cooling_power = 0.0
            self._last_mode = "heating"  # <-- AJOUT
        elif cooling_power > 0 and compressor_running:
            # On ne comptabilise le froid que compresseur en marche
            self._accumulator.update(cooling_power, mode="cooling")
            self._last_cooling_power = cooling_power
            self._last_heating_power = 0.0
            self._last_mode = "cooling"  # <-- AJOUT
        else:
            # Pas de puissance significative
            # On avance quand même l'horloge de l'accumulateur avec 0 kW
            if self._last_mode is not None:
                self._accumulator.update(0.0, mode=self._last_mode)

            self._last_heating_power = 0.0
            self._last_cooling_power = 0.0

    def get_heating_power(self) -> float:
        """Get current heating power in kW."""
        return round(self._last_heating_power, 2) if self._last_heating_power > 0 else 0

    def get_cooling_power(self) -> float:
        """Get current cooling power in kW."""
        return round(self._last_cooling_power, 2) if self._last_cooling_power > 0 else 0

    def get_daily_heating_energy(self) -> float:
        """Get daily heating energy in kWh."""
        return round(self._accumulator.daily_heating_energy, 2)

    def get_total_heating_energy(self) -> float:
        """Get total heating energy in kWh."""
        return round(self._accumulator.total_heating_energy, 2)

    def get_daily_cooling_energy(self) -> float:
        """Get daily cooling energy in kWh."""
        return round(self._accumulator.daily_cooling_energy, 2)

    def get_total_cooling_energy(self) -> float:
        """Get total cooling energy in kWh."""
        return round(self._accumulator.total_cooling_energy, 2)

    def restore_daily_heating_energy(self, energy: float) -> None:
        """Restore daily heating energy state (used after HA restart).

        Args:
            energy: Energy value to restore

        """
        self._accumulator.restore_daily_heating_energy(energy)

    def restore_total_heating_energy(self, energy: float) -> None:
        """Restore total heating energy state (used after HA restart).

        Args:
            energy: Energy value to restore

        """
        self._accumulator.restore_total_heating_energy(energy)

    def restore_daily_cooling_energy(self, energy: float) -> None:
        """Restore daily cooling energy state (used after HA restart).

        Args:
            energy: Energy value to restore

        """
        self._accumulator.restore_daily_cooling_energy(energy)

    def restore_total_cooling_energy(self, energy: float) -> None:
        """Restore total cooling energy state (used after HA restart).

        Args:
            energy: Energy value to restore

        """
        self._accumulator.restore_total_cooling_energy(energy)
