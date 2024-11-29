"""Select platform for Hitachi Yutaki."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_CONTROL_UNIT,
    DOMAIN,
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
        translation_key="operation_mode_heat",
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
        translation_key="operation_mode_full",
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
        key="otc_calculation_method_heating",
        translation_key="otc_calculation_method_heating",
        description="Method used to calculate the heating water temperature based on outdoor temperature (OTC - Outdoor Temperature Compensation)",
        register_key="otc_calculation_method_heating",
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
        key="otc_calculation_method_cooling",
        translation_key="otc_calculation_method_cooling",
        description="Method used to calculate the cooling water temperature based on outdoor temperature (OTC - Outdoor Temperature Compensation)",
        register_key="otc_calculation_method_cooling",
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

    # Add circuit selects only if the circuits are configured
    if coordinator.has_heating_circuit1():
        entities.extend(
            HitachiYutakiSelect(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_1}")},
                ),
                register_prefix="circuit1",
            )
            for description in CIRCUIT_SELECTS
            if description.condition is None or description.condition(coordinator, 1)
        )

    if coordinator.has_heating_circuit2():
        entities.extend(
            HitachiYutakiSelect(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_2}")},
                ),
                register_prefix="circuit2",
            )
            for description in CIRCUIT_SELECTS
            if description.condition is None or description.condition(coordinator, 2)
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
