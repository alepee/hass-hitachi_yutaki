"""Thermal energy accumulator for heating and cooling.

Pure business logic isolated from infrastructure concerns.
"""

from __future__ import annotations

from datetime import date, datetime
from time import time

from ...models.operation import (
    HEATING_ONLY_MODES,
    MODE_COOLING,
    MODE_HEATING,
)


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
        self._post_cycle_lock = False
        self._last_mode: str | None = None

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
    def last_heating_power(self) -> float:
        """Return the last effective heating power in kW."""
        return self._last_heating_power

    @property
    def last_cooling_power(self) -> float:
        """Return the last effective cooling power in kW."""
        return self._last_cooling_power

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

    def update(
        self,
        heating_power: float,
        cooling_power: float,
        compressor_running: bool,
        operation_mode: str | None = None,
    ) -> None:
        """Update energy accumulation with thermal powers.

        Args:
            heating_power: Positive thermal power (delta T > 0)
            cooling_power: Positive thermal power (delta T < 0, already negated)
            compressor_running: Whether compressor is active
            operation_mode: Current operation mode (e.g. MODE_HEATING, MODE_COOLING,
                MODE_DHW, MODE_POOL). DHW and pool are always heating operations.

        """
        # DHW and pool are always heating operations regardless of ΔT.
        # When the unit switches from cooling circuits to DHW, the water
        # temperature sensors may still reflect circuit temps briefly,
        # producing a negative ΔT that would be incorrectly classified
        # as cooling energy.
        if operation_mode in HEATING_ONLY_MODES:
            # Use the absolute thermal power as heating, ignore cooling
            total_power = heating_power + cooling_power
            heating_power = total_power
            cooling_power = 0.0

        # If compressor restarts, exit post-cycle lock
        if compressor_running:
            self._post_cycle_lock = False

        # Handle inertia and post-cycle lock (both modes)
        if not compressor_running:
            # Activate lock when delta T drops to zero in current mode
            if (
                self._last_mode == MODE_HEATING
                and heating_power <= 0
                or self._last_mode == MODE_COOLING
                and cooling_power <= 0
            ):
                self._post_cycle_lock = True

            # When locked, force power to 0 for current mode
            if self._post_cycle_lock:
                if self._last_mode == MODE_HEATING:
                    heating_power = 0.0
                elif self._last_mode == MODE_COOLING:
                    cooling_power = 0.0

        # Mode decision and accumulation
        if heating_power > 0:
            self._update_energy(heating_power, mode=MODE_HEATING)
            self._last_mode = MODE_HEATING
            self._last_heating_power = heating_power
            self._last_cooling_power = 0.0
        elif cooling_power > 0:
            # Count cooling energy including thermal inertia after compressor stops
            self._update_energy(cooling_power, mode=MODE_COOLING)
            self._last_mode = MODE_COOLING
            self._last_cooling_power = cooling_power
            self._last_heating_power = 0.0
        else:
            # No significant power
            # Still advance accumulator clock with 0 kW
            if self._last_mode is not None:
                self._update_energy(0.0, mode=self._last_mode)
            self._last_heating_power = 0.0
            self._last_cooling_power = 0.0

    def _update_energy(self, thermal_power: float, mode: str) -> None:
        """Update energy accumulation.

        Args:
            thermal_power: Current thermal power in kW
            mode: Operating mode (MODE_HEATING or MODE_COOLING)

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

            if mode == MODE_HEATING:
                avg_power = (thermal_power + self._last_heating_power) / 2
                energy = avg_power * time_diff_hours
                self._daily_heating_energy += energy
                self._total_heating_energy += energy
                # Note: last power updates are handled in update() method
            elif mode == MODE_COOLING:
                avg_power = (thermal_power + self._last_cooling_power) / 2
                energy = avg_power * time_diff_hours
                self._daily_cooling_energy += energy
                self._total_cooling_energy += energy
                # Note: last power updates are handled in update() method

        self._last_measurement_time = current_time
