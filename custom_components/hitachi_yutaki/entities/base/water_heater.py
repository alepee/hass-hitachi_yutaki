"""Base water heater entity for Hitachi Yutaki integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...const import PRESET_DHW_HEAT_PUMP, PRESET_DHW_HIGH_DEMAND, PRESET_DHW_OFF
from ...coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiWaterHeaterEntityDescription(WaterHeaterEntityDescription):
    """Class describing Hitachi Yutaki water heater entities."""

    key: str
    translation_key: str
    description: str | None = None


class HitachiYutakiWaterHeater(
    CoordinatorEntity[HitachiYutakiDataCoordinator], WaterHeaterEntity
):
    """Representation of a Hitachi Yutaki Water Heater."""

    entity_description: HitachiYutakiWaterHeaterEntityDescription

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiWaterHeaterEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the water heater."""
        super().__init__(coordinator)
        self.entity_description = description
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        # Apply profile-specific overrides
        self._apply_profile_overrides()

        self._attr_target_temperature_step = 1
        self._attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE
            | WaterHeaterEntityFeature.ON_OFF
        )
        self._attr_operation_list = [
            PRESET_DHW_OFF,
            PRESET_DHW_HEAT_PUMP,
            PRESET_DHW_HIGH_DEMAND,
        ]

    def _apply_profile_overrides(self) -> None:
        """Apply overrides from the heat pump profile."""
        if not self.coordinator.profile:
            self._attr_min_temp = 30
            self._attr_max_temp = 60
            return

        overrides = self.coordinator.profile.entity_overrides.get("water_heater", {})
        self._attr_min_temp = overrides.get("min_temp", 30)
        self._attr_max_temp = overrides.get("max_temp", 60)
        self._temperature_entity_key = overrides.get(
            "temperature_entity_key", "dhw_target_temp"
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data is None:
            return None

        return self.coordinator.api_client.get_dhw_current_temperature()

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.coordinator.data is None:
            return None

        return self.coordinator.api_client.get_dhw_target_temperature()

    @property
    def current_operation(self) -> str | None:
        """Return current operation."""
        if self.coordinator.data is None:
            return None

        power = self.coordinator.api_client.get_dhw_power()
        if not power:
            return PRESET_DHW_OFF

        high_demand = self.coordinator.api_client.get_dhw_high_demand()
        if high_demand:
            return PRESET_DHW_HIGH_DEMAND

        return PRESET_DHW_HEAT_PUMP

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        operation = self.current_operation
        if operation == PRESET_DHW_OFF:
            return "mdi:water-boiler-off"
        elif operation == PRESET_DHW_HIGH_DEMAND:
            return "mdi:water-boiler-alert"
        return "mdi:water-boiler"

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        await self.coordinator.api_client.set_dhw_target_temperature(temperature)
        await self.coordinator.async_request_refresh()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        if operation_mode == PRESET_DHW_OFF:
            # First disable high demand mode if it was active
            await self.coordinator.api_client.set_dhw_high_demand(False)
            # Then turn off DHW
            await self.coordinator.api_client.set_dhw_power(False)
            await self.coordinator.async_request_refresh()
            return

        # First ensure DHW is turned on if it was off
        current_power = self.coordinator.api_client.get_dhw_power()
        if not current_power:
            await self.coordinator.api_client.set_dhw_power(True)

        # Then set the mode
        if operation_mode == PRESET_DHW_HIGH_DEMAND:
            await self.coordinator.api_client.set_dhw_high_demand(True)
        elif operation_mode == PRESET_DHW_HEAT_PUMP:
            await self.coordinator.api_client.set_dhw_high_demand(False)

        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        await self.coordinator.api_client.set_dhw_power(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        # First disable high demand mode if it was active
        await self.coordinator.api_client.set_dhw_high_demand(False)
        # Then turn off DHW
        await self.coordinator.api_client.set_dhw_power(False)
        await self.coordinator.async_request_refresh()

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        return self.hass.async_add_executor_job(self.async_set_temperature, **kwargs)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        return self.hass.async_add_executor_job(self.async_turn_on, **kwargs)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        return self.hass.async_add_executor_job(self.async_turn_off, **kwargs)

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        return self.hass.async_add_executor_job(
            self.async_set_operation_mode, operation_mode
        )

    def turn_away_mode_off(self, **kwargs: Any) -> None:
        """Turn away mode off - Not supported."""
        raise NotImplementedError("Away mode is not supported")

    def turn_away_mode_on(self, **kwargs: Any) -> None:
        """Turn away mode on - Not supported."""
        raise NotImplementedError("Away mode is not supported")
