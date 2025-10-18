"""Number platform for Hitachi Yutaki."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_DHW,
    DEVICE_POOL,
    DOMAIN,
)
from .coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiNumberEntityDescription(NumberEntityDescription):
    """Class describing Hitachi Yutaki number entities."""

    key: str
    translation_key: str
    max_value: None = None
    min_value: None = None
    mode: NumberMode | None = None
    native_max_value: float | None = None
    native_min_value: float | None = None
    native_step: float | None = None
    native_unit_of_measurement: str | None = None
    step: None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True

    description: str | None = None
    get_fn: Callable[[Any, int | None], float | None] | None = None
    set_fn: Callable[[Any, int | None, float], Any] | None = None


CIRCUIT_NUMBERS: Final[tuple[HitachiYutakiNumberEntityDescription, ...]] = (
    HitachiYutakiNumberEntityDescription(
        key="max_flow_temp_heating_otc",
        translation_key="max_flow_temp_heating_otc",
        description="Maximum heating water temperature used in outdoor temperature compensation (OTC) calculations",
        native_min_value=0,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_fn=lambda api, circuit_id: api.get_circuit_max_flow_temp_heating(
            circuit_id
        ),
        set_fn=lambda api, circuit_id, value: api.set_circuit_max_flow_temp_heating(
            circuit_id, value
        ),
    ),
    HitachiYutakiNumberEntityDescription(
        key="max_flow_temp_cooling_otc",
        translation_key="max_flow_temp_cooling_otc",
        description="Maximum cooling water temperature used in outdoor temperature compensation (OTC) calculations",
        native_min_value=0,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_fn=lambda api, circuit_id: api.get_circuit_max_flow_temp_cooling(
            circuit_id
        ),
        set_fn=lambda api, circuit_id, value: api.set_circuit_max_flow_temp_cooling(
            circuit_id, value
        ),
    ),
    HitachiYutakiNumberEntityDescription(
        key="heat_eco_offset",
        translation_key="heat_eco_offset",
        description="Temperature offset applied in ECO mode for heating",
        native_min_value=1,
        native_max_value=10,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda api, circuit_id: float(value)
        if (value := api.get_circuit_heat_eco_offset(circuit_id)) is not None
        else None,
        set_fn=lambda api, circuit_id, value: api.set_circuit_heat_eco_offset(
            circuit_id, int(value)
        ),
    ),
    HitachiYutakiNumberEntityDescription(
        key="cool_eco_offset",
        translation_key="cool_eco_offset",
        description="Temperature offset applied in ECO mode for cooling",
        native_min_value=1,
        native_max_value=10,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda api, circuit_id: float(value)
        if (value := api.get_circuit_cool_eco_offset(circuit_id)) is not None
        else None,
        set_fn=lambda api, circuit_id, value: api.set_circuit_cool_eco_offset(
            circuit_id, int(value)
        ),
    ),
)

DHW_NUMBERS: Final[tuple[HitachiYutakiNumberEntityDescription, ...]] = (
    HitachiYutakiNumberEntityDescription(
        key="antilegionella_temp",
        translation_key="antilegionella_temp",
        description="Target temperature for anti-legionella treatment",
        native_min_value=60,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_fn=lambda api, _: api.get_dhw_antilegionella_temperature(),
        set_fn=lambda api, _, value: api.set_dhw_antilegionella_temperature(value),
    ),
)

POOL_NUMBERS: Final[tuple[HitachiYutakiNumberEntityDescription, ...]] = (
    HitachiYutakiNumberEntityDescription(
        key="pool_target_temp",
        translation_key="pool_target_temperature",
        description="Target temperature for swimming pool water",
        native_min_value=0,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda api, _: api.get_pool_target_temperature(),
        set_fn=lambda api, _, value: api.set_pool_target_temperature(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number entities."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[HitachiYutakiNumber] = []

    # Add circuit 1 numbers if configured
    if coordinator.has_heating_circuit1():
        for description in CIRCUIT_NUMBERS:
            # Skip cooling related entities if cooling is not available
            if "cool" in description.key and not coordinator.has_cooling_circuit1():
                continue
            entities.append(
                HitachiYutakiNumber(
                    coordinator=coordinator,
                    description=description,
                    device_info=DeviceInfo(
                        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_1}")},
                    ),
                    register_prefix="circuit1",
                )
            )

    # Add circuit 2 numbers if configured
    if coordinator.has_heating_circuit2():
        for description in CIRCUIT_NUMBERS:
            # Skip cooling related entities if cooling is not available
            if "cool" in description.key and not coordinator.has_cooling_circuit2():
                continue
            entities.append(
                HitachiYutakiNumber(
                    coordinator=coordinator,
                    description=description,
                    device_info=DeviceInfo(
                        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_2}")},
                    ),
                    register_prefix="circuit2",
                )
            )

    # Add DHW numbers if configured
    if coordinator.has_dhw():
        entities.extend(
            HitachiYutakiNumber(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DHW}")},
                ),
                register_prefix="dhw",
            )
            for description in DHW_NUMBERS
        )

    # Add pool numbers if configured
    if coordinator.has_pool():
        entities.extend(
            HitachiYutakiNumber(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_POOL}")},
                ),
                register_prefix="pool",
            )
            for description in POOL_NUMBERS
        )

    async_add_entities(entities)


class HitachiYutakiNumber(
    CoordinatorEntity[HitachiYutakiDataCoordinator], NumberEntity
):
    """Representation of a Hitachi Yutaki Number."""

    entity_description: HitachiYutakiNumberEntityDescription

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiNumberEntityDescription,
        device_info: DeviceInfo,
        register_prefix: str | None = None,
    ) -> None:
        """Initialize the number entity."""
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
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        if self.coordinator.data is None or not self.entity_description.get_fn:
            return None

        return self.entity_description.get_fn(
            self.coordinator.api_client, self._circuit_id
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.set_fn:
            await self.entity_description.set_fn(
                self.coordinator.api_client, self._circuit_id, value
            )
            await self.coordinator.async_request_refresh()

    def set_native_value(self, value: float) -> None:
        """Set new value."""
        raise NotImplementedError
