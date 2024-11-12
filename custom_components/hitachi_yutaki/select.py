"""Select platform for Hitachi Yutaki."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Final

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DEVICE_CONTROL_UNIT,
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_DHW,
)
from .coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiSelectEntityDescription(SelectEntityDescription):
    """Class describing Hitachi Yutaki select entities."""

    register_key: str | None = None
    value_map: dict[str, int] | None = None


UNIT_SELECTS: Final[tuple[HitachiYutakiSelectEntityDescription, ...]] = (
    HitachiYutakiSelectEntityDescription(
        key="operation_mode",
        name="Operation Mode",
        register_key="unit_mode",
        options=["cool", "heat", "auto"],
        value_map={
            "cool": 0,
            "heat": 1,
            "auto": 2,
        },
    ),
)

CIRCUIT_SELECTS: Final[tuple[HitachiYutakiSelectEntityDescription, ...]] = (
    HitachiYutakiSelectEntityDescription(
        key="heat_mode",
        name="Heat Mode",
        register_key="heat_mode",
        options=["disabled", "points", "gradient", "fix"],
        value_map={
            "disabled": 0,
            "points": 1,
            "gradient": 2,
            "fix": 3,
        },
    ),
    HitachiYutakiSelectEntityDescription(
        key="cool_mode",
        name="Cool Mode",
        register_key="cool_mode",
        options=["disabled", "points", "fix"],
        value_map={
            "disabled": 0,
            "points": 1,
            "fix": 2,
        },
    ),
    HitachiYutakiSelectEntityDescription(
        key="eco_mode",
        name="ECO Mode",
        register_key="eco_mode",
        options=["eco", "comfort"],
        value_map={
            "eco": 0,
            "comfort": 1,
        },
    ),
)

DHW_SELECTS: Final[tuple[HitachiYutakiSelectEntityDescription, ...]] = (
    HitachiYutakiSelectEntityDescription(
        key="dhw_mode",
        name="DHW Mode",
        register_key="dhw_mode",
        options=["standard", "high_demand"],
        value_map={
            "standard": 0,
            "high_demand": 1,
        },
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
    )

    # Add circuit 1 selects if configured
    if coordinator.has_heating_circuit1():
        for description in CIRCUIT_SELECTS:
            if description.key == "cool_mode" and not coordinator.has_cooling_circuit1():
                continue
            entities.append(
                HitachiYutakiSelect(
                    coordinator=coordinator,
                    description=description,
                    device_info=DeviceInfo(
                        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_1}")},
                    ),
                    register_prefix="circuit1",
                )
            )

    # Add circuit 2 selects if configured
    if coordinator.has_heating_circuit2():
        for description in CIRCUIT_SELECTS:
            if description.key == "cool_mode" and not coordinator.has_cooling_circuit2():
                continue
            entities.append(
                HitachiYutakiSelect(
                    coordinator=coordinator,
                    description=description,
                    device_info=DeviceInfo(
                        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_2}")},
                    ),
                    register_prefix="circuit2",
                )
            )

    # Add DHW selects if configured
    if coordinator.has_dhw():
        entities.extend(
            HitachiYutakiSelect(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DHW}")},
                ),
            )
            for description in DHW_SELECTS
        )

    async_add_entities(entities)


class HitachiYutakiSelect(
    CoordinatorEntity[HitachiYutakiDataCoordinator], SelectEntity
):
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
        self._register_key = (
            f"{register_prefix}_{description.register_key}"
            if register_prefix
            else description.register_key
        )
        self._attr_unique_id = f"{coordinator.slave}_{register_prefix}_{description.key}" if register_prefix else f"{coordinator.slave}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if (
            self.coordinator.data is None
            or self.entity_description.value_map is None
            or self._register_key is None
        ):
            return None

        value = self.coordinator.data.get(self._register_key)
        if value is None:
            return None

        # Find the key in value_map that corresponds to the register value
        for key, val in self.entity_description.value_map.items():
            if val == value:
                return key

        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if (
            self.entity_description.value_map is None
            or self._register_key is None
            or option not in self.entity_description.value_map
        ):
            return

        value = self.entity_description.value_map[option]
        await self.coordinator.async_write_register(self._register_key, value)
