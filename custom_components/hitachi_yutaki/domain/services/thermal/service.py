"""Thermal power service for orchestrating calculations.

Pure business logic isolated from infrastructure concerns.
"""

from __future__ import annotations

from ...models.thermal import ThermalPowerInput
from .accumulator import ThermalEnergyAccumulator
from .calculators import calculate_thermal_power_cooling, calculate_thermal_power_heating


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
        # Compressor running status
        compressor_running = (
            compressor_frequency is not None and compressor_frequency > 0
        )

        # Validate input data or handle defrost
        if is_defrosting or any(
            x is None for x in [water_inlet_temp, water_outlet_temp, water_flow]
        ):
            self._accumulator.update(
                heating_power=0.0,
                cooling_power=0.0,
                compressor_running=compressor_running,
                is_defrosting=is_defrosting,
            )
            return

        # Power calculation (pure calculation, no business logic)
        thermal_input = ThermalPowerInput(
            water_inlet_temp,  # type: ignore
            water_outlet_temp,  # type: ignore
            water_flow,  # type: ignore
        )
        heating_power = calculate_thermal_power_heating(thermal_input)
        cooling_power = calculate_thermal_power_cooling(thermal_input)

        # Delegate all logic to accumulator
        self._accumulator.update(
            heating_power=heating_power,
            cooling_power=cooling_power,
            compressor_running=compressor_running,
            is_defrosting=is_defrosting,
        )

    def get_heating_power(self) -> float:
        """Get current heating power in kW."""
        return round(self._accumulator.last_heating_power, 2)

    def get_cooling_power(self) -> float:
        """Get current cooling power in kW."""
        return round(self._accumulator.last_cooling_power, 2)

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
