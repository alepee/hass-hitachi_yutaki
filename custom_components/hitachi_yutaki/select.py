"""Select platform for Hitachi Yutaki."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.climate import HVACMode
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
    OTCCalculationMethod,
)
from .coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiSelectEntityDescription(SelectEntityDescription):
    """Class describing Hitachi Yutaki select entities."""

    key: str
    translation_key: str
    options: list[str] | None = None

    value_map: dict[str, Any] | None = None
    condition: callable | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = False
    description: str | None = None
    get_fn: Callable[[Any, int | None], str | None] | None = None
    set_fn: Callable[[Any, int | None, Any], Any] | None = None


UNIT_SELECTS: Final[tuple[HitachiYutakiSelectEntityDescription, ...]] = (
    HitachiYutakiSelectEntityDescription(
        key="operation_mode_heat",
        translation_key="operation_mode_heat",
        description="Operating mode of the heat pump (heating only unit)",
        options=["heat", "auto"],
        value_map={
            "heat": HVACMode.HEAT,
            "auto": HVACMode.AUTO,
        },
        condition=lambda coordinator: not (
            coordinator.has_circuit1_cooling() or coordinator.has_circuit2_cooling()
        ),
        get_fn=lambda api, _: api.get_unit_mode(),
        set_fn=lambda api, _, value: api.set_unit_mode(value),
    ),
    HitachiYutakiSelectEntityDescription(
        key="operation_mode_full",
        translation_key="operation_mode_full",
        description="Operating mode of the heat pump (heating and cooling unit)",
        options=["cool", "heat", "auto"],
        value_map={
            "cool": HVACMode.COOL,
            "heat": HVACMode.HEAT,
            "auto": HVACMode.AUTO,
        },
        condition=lambda coordinator: coordinator.has_circuit1_cooling()
        or coordinator.has_circuit2_cooling(),
        get_fn=lambda api, _: api.get_unit_mode(),
        set_fn=lambda api, _, value: api.set_unit_mode(value),
    ),
)

CIRCUIT_SELECTS: Final[tuple[HitachiYutakiSelectEntityDescription, ...]] = (
    HitachiYutakiSelectEntityDescription(
        key="otc_calculation_method_heating",
        translation_key="otc_calculation_method_heating",
        description="Method used to calculate the heating water temperature based on outdoor temperature (OTC - Outdoor Temperature Compensation)",
        options=["disabled", "points", "gradient", "fix"],
        value_map={
            "disabled": OTCCalculationMethod.DISABLED,
            "points": OTCCalculationMethod.POINTS,
            "gradient": OTCCalculationMethod.GRADIENT,
            "fix": OTCCalculationMethod.FIX,
        },
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_fn=lambda api, circuit_id: api.get_circuit_otc_method_heating(circuit_id),
        set_fn=lambda api, circuit_id, value: api.set_circuit_otc_method_heating(
            circuit_id, value
        ),
    ),
    HitachiYutakiSelectEntityDescription(
        key="otc_calculation_method_cooling",
        translation_key="otc_calculation_method_cooling",
        description="Method used to calculate the cooling water temperature based on outdoor temperature (OTC - Outdoor Temperature Compensation)",
        options=["disabled", "points", "fix"],
        value_map={
            "disabled": OTCCalculationMethod.DISABLED,
            "points": OTCCalculationMethod.POINTS,
            "fix": OTCCalculationMethod.FIX,
        },
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        condition=lambda coordinator, circuit_id: getattr(
            coordinator, f"has_circuit{circuit_id}_cooling"
        )(),
        get_fn=lambda api, circuit_id: api.get_circuit_otc_method_cooling(circuit_id),
        set_fn=lambda api, circuit_id, value: api.set_circuit_otc_method_cooling(
            circuit_id, value
        ),
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
    if coordinator.has_circuit1_heating():
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

    if coordinator.has_circuit2_heating():
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
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = (
            f"{entry_id}_{register_prefix}_{description.key}"
            if register_prefix
            else f"{entry_id}_{description.key}"
        )
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

        # Extract circuit_id if applicable
        self._circuit_id = (
            int(register_prefix.replace("circuit", ""))
            if register_prefix and register_prefix.startswith("circuit")
            else None
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if (
            not self.coordinator.data
            or not self.entity_description.value_map
            or not self.entity_description.get_fn
        ):
            return None

        value = self.entity_description.get_fn(
            self.coordinator.api_client, self._circuit_id
        )

        if value is None:
            return None

        return next(
            (k for k, v in self.entity_description.value_map.items() if v == value),
            None,
        )

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        raise NotImplementedError("Async version should be used instead")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if (
            not self.entity_description.value_map
            or option not in self.entity_description.value_map
            or not self.entity_description.set_fn
        ):
            return

        value = self.entity_description.value_map[option]
        await self.entity_description.set_fn(
            self.coordinator.api_client, self._circuit_id, value
        )
        await self.coordinator.async_request_refresh()
