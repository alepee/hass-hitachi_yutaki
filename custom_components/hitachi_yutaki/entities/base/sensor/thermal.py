"""Thermal energy sensor for Hitachi Yutaki."""

from __future__ import annotations

from contextlib import suppress

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from ....adapters.providers.operation_mode import resolve_operation_mode
from ....const import (
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
)
from ....coordinator import HitachiYutakiDataCoordinator
from ....domain.services.thermal import ThermalEnergyAccumulator, ThermalPowerService
from .base import HitachiYutakiSensor, HitachiYutakiSensorEntityDescription


class HitachiYutakiThermalSensor(HitachiYutakiSensor):
    """Sensor for thermal energy measurements."""

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiSensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the thermal sensor."""
        super().__init__(coordinator, description, device_info)
        accumulator = ThermalEnergyAccumulator()
        self._thermal_service = ThermalPowerService(accumulator=accumulator)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        await self._async_restore_thermal_energy()

    def _is_same_day_reset(self, state) -> bool:
        """Check if the last reset was today."""
        last_reset_str = state.attributes.get("last_reset")
        if not last_reset_str:
            return False
        with suppress(ValueError):
            last_reset = dt_util.parse_datetime(last_reset_str)
            if last_reset is None:
                return False
            now = dt_util.now()
            return last_reset.date() == now.date()
        return False

    def _get_thermal_data(self) -> tuple[float, float, float] | None:
        """Get thermal data (inlet, outlet, flow) or None if any is missing."""
        if self.coordinator.data is None:
            return None

        water_inlet = self._get_temperature(
            CONF_WATER_INLET_TEMP_ENTITY, "water_inlet_temp"
        )
        water_outlet = self._get_temperature(
            CONF_WATER_OUTLET_TEMP_ENTITY, "water_outlet_temp"
        )
        water_flow = self.coordinator.data.get("water_flow")

        if None in (water_inlet, water_outlet, water_flow):
            return None

        return water_inlet, water_outlet, water_flow  # type: ignore

    def _update_thermal_energy(self) -> None:
        """Update thermal energy using the thermal sensor service."""
        thermal_data = self._get_thermal_data()
        if thermal_data is None:
            return

        water_inlet, water_outlet, water_flow = thermal_data

        if not self.coordinator.defrost_guard.is_data_reliable:
            water_inlet = None
            water_outlet = None

        # Map operation_state to domain-level mode for correct energy classification.
        # DHW and pool are always heating operations regardless of temperature delta.
        operation_state_raw = self.coordinator.data.get("operation_state")
        operation_mode = resolve_operation_mode(operation_state_raw)

        self._thermal_service.update(
            water_inlet_temp=water_inlet,
            water_outlet_temp=water_outlet,
            water_flow=water_flow,
            compressor_frequency=self.coordinator.data.get("compressor_frequency"),
            operation_mode=operation_mode,
        )

    async def _async_restore_thermal_energy(self) -> None:
        """Restore thermal energy state from the Recorder/last state cache."""
        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        with suppress(ValueError):
            energy_value = float(last_state.state)
            # New heating/cooling sensors
            if self.entity_description.key == "thermal_energy_heating_total":
                self._thermal_service.restore_total_heating_energy(energy_value)
            elif self.entity_description.key == "thermal_energy_heating_daily":
                if self._is_same_day_reset(last_state):
                    self._thermal_service.restore_daily_heating_energy(energy_value)
            elif self.entity_description.key == "thermal_energy_cooling_total":
                self._thermal_service.restore_total_cooling_energy(energy_value)
            elif self.entity_description.key == "thermal_energy_cooling_daily":
                if self._is_same_day_reset(last_state):
                    self._thermal_service.restore_daily_cooling_energy(energy_value)

    @property
    def native_value(self) -> StateType:
        """Return the thermal sensor value."""
        if self.coordinator.data is None:
            return None

        self._update_thermal_energy()

        key = self.entity_description.key
        if key == "thermal_power_heating":
            return self._thermal_service.get_heating_power()
        elif key == "thermal_power_cooling":
            return self._thermal_service.get_cooling_power()
        elif key == "thermal_energy_heating_daily":
            return self._thermal_service.get_daily_heating_energy()
        elif key == "thermal_energy_heating_total":
            return self._thermal_service.get_total_heating_energy()
        elif key == "thermal_energy_cooling_daily":
            return self._thermal_service.get_daily_cooling_energy()
        elif key == "thermal_energy_cooling_total":
            return self._thermal_service.get_total_cooling_energy()

        return None
