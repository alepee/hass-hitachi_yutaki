"""Select platform for Hitachi Yutaki."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Final

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import EntityCategory

from .const import (
    DOMAIN,
    DEVICE_CONTROL_UNIT,
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_DHW,
    MODEL_NAMES,
)
from .coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiSelectEntityDescription(SelectEntityDescription):
    """Class describing Hitachi Yutaki select entities."""
    register_key: str | None = None
    value_map: dict[str, int] | None = None
    condition: callable | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = False
    description: str | None = None


UNIT_SELECTS: Final[tuple[HitachiYutakiSelectEntityDescription, ...]] = (
    HitachiYutakiSelectEntityDescription(
        key="operation_mode_heat",
        name="Operation Mode",
        description="Operating mode of the heat pump (heating only unit)",
        register_key="unit_mode",
        options=["heat", "auto"],
        value_map={
            "heat": 1,
            "auto": 2,
        },
        condition=lambda coordinator: not (coordinator.has_cooling_circuit1() or coordinator.has_cooling_circuit2()),
    ),
    HitachiYutakiSelectEntityDescription(
        key="operation_mode_full",
        name="Operation Mode",
        description="Operating mode of the heat pump (heating and cooling unit)",
        register_key="unit_mode",
        options=["cool", "heat", "auto"],
        value_map={
            "cool": 0,
            "heat": 1,
            "auto": 2,
        },
        condition=lambda coordinator: coordinator.has_cooling_circuit1() or coordinator.has_cooling_circuit2(),
    ),
)

CIRCUIT_SELECTS: Final[tuple[HitachiYutakiSelectEntityDescription, ...]] = (
    HitachiYutakiSelectEntityDescription(
        key="water_heating_temp_control",
        name="Water Heating Temperature Control",
        description="Method used to calculate the water temperature setpoint based on outdoor temperature (Weather compensation)",
        register_key="water_heating_temp_control",
        options=["disabled", "points", "gradient", "fix"],
        value_map={
            "disabled": 0,
            "points": 1,
            "gradient": 2,
            "fix": 3,
        },
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HitachiYutakiSelectEntityDescription(
        key="water_cooling_temp_control",
        name="Water Cooling Temperature Control",
        description="Method used to calculate the water temperature setpoint based on outdoor temperature (Weather compensation)",
        register_key="water_cooling_temp_control",
        options=["disabled", "points", "fix"],
        value_map={
            "disabled": 0,
            "points": 1,
            "fix": 2,
        },
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        condition=lambda coordinator, circuit_id: getattr(coordinator, f"has_cooling_circuit{circuit_id}")(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the selects."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[HitachiYutakiSelect] = []

    # Add unit selects
    entities.extend(
        HitachiYutakiSelect(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
            ),
        )
        for description in UNIT_SELECTS
        if description.condition is None or description.condition(coordinator)
    )

    # Add circuit selects
    for circuit_id, device_id in [(1, DEVICE_CIRCUIT_1), (2, DEVICE_CIRCUIT_2)]:
        entities.extend(
            HitachiYutakiSelect(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{device_id}")},
                ),
                register_prefix=f"circuit{circuit_id}",
            )
            for description in CIRCUIT_SELECTS
            if description.condition is None or description.condition(coordinator, circuit_id)
        )

    async_add_entities(entities)


class HitachiYutakiSelect(CoordinatorEntity[HitachiYutakiDataCoordinator], SelectEntity):
    """Representation of a Hitachi Yutaki Select."""

    entity_description: HitachiYutakiSelectEntityDescription

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiSelectEntityDescription,
        device_info: DeviceInfo,
        register_prefix: str | None = None,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self.entity_description = description
        self.register_prefix = register_prefix
        self._register_key = f"{register_prefix}_{description.register_key}" if register_prefix else description.register_key
        self._attr_unique_id = f"{coordinator.slave}_{register_prefix}_{description.key}" if register_prefix else f"{coordinator.slave}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if not self.coordinator.data or not self.entity_description.value_map or not self._register_key:
            return None

        value = self.coordinator.data.get(self._register_key)
        if value is None:
            return None

        return next(
            (k for k, v in self.entity_description.value_map.items() if v == value),
            None
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if not self.entity_description.value_map or not self._register_key or option not in self.entity_description.value_map:
            return

        await self.coordinator.async_write_register(
            self._register_key,
            self.entity_description.value_map[option]
        )
