"""Water heater platform for Hitachi Yutaki."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_DHW,
    DOMAIN,
    PRESET_DHW_HIGH_DEMAND,
    PRESET_DHW_OFF,
    PRESET_DHW_STANDARD,
)
from .coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiWaterHeaterEntityDescription(WaterHeaterEntityDescription):
    """Class describing Hitachi Yutaki water heater entities."""

    key: str
    translation_key: str
    description: str | None = None


WATER_HEATERS: Final[tuple[HitachiYutakiWaterHeaterEntityDescription, ...]] = (
    HitachiYutakiWaterHeaterEntityDescription(
        key="dhw",
        translation_key="dhw",
        description="Domestic hot water production",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the water heater."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[HitachiYutakiWaterHeater] = []

    # Add DHW water heater if configured
    if coordinator.has_dhw():
        entities.extend(
            HitachiYutakiWaterHeater(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DHW}")},
                ),
            )
            for description in WATER_HEATERS
        )

    async_add_entities(entities)


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
        self._register_prefix = "dhw"
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{coordinator.slave}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_min_temp = 30
        self._attr_max_temp = 60
        self._attr_target_temperature_step = 1
        self._attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE
            | WaterHeaterEntityFeature.ON_OFF
        )
        self._attr_operation_list = [
            PRESET_DHW_OFF,
            PRESET_DHW_STANDARD,
            PRESET_DHW_HIGH_DEMAND,
        ]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data is None:
            return None

        temp = self.coordinator.data.get("dhw_current_temp")
        if temp is None:
            return None

        return float(self.coordinator.convert_temperature(temp))

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.coordinator.data is None:
            return None

        temp = self.coordinator.data.get("dhw_target_temp")
        if temp is None:
            return None

        return float(temp)

    @property
    def current_operation(self) -> str | None:
        """Return current operation."""
        if self.coordinator.data is None:
            return None

        power = self.coordinator.data.get("dhw_power")
        if power == 0:
            return PRESET_DHW_OFF

        high_demand = self.coordinator.data.get("dhw_high_demand")
        if high_demand == 1:
            return PRESET_DHW_HIGH_DEMAND

        return PRESET_DHW_STANDARD

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

        await self.coordinator.async_write_register(
            "dhw_target_temp", int(temperature)
        )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        if operation_mode == PRESET_DHW_OFF:
            # First disable high demand mode if it was active
            await self.coordinator.async_write_register("dhw_high_demand", 0)
            # Then turn off DHW
            await self.coordinator.async_write_register("dhw_power", 0)
            return

        # First ensure DHW is turned on if it was off
        current_power = self.coordinator.data.get("dhw_power", 0)
        if current_power == 0:
            await self.coordinator.async_write_register("dhw_power", 1)

        # Then set the mode
        if operation_mode == PRESET_DHW_HIGH_DEMAND:
            await self.coordinator.async_write_register("dhw_high_demand", 1)
        elif operation_mode == PRESET_DHW_STANDARD:
            await self.coordinator.async_write_register("dhw_high_demand", 0)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        await self.coordinator.async_write_register("dhw_power", 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        # First disable high demand mode if it was active
        await self.coordinator.async_write_register("dhw_high_demand", 0)
        # Then turn off DHW
        await self.coordinator.async_write_register("dhw_power", 0)
