"""Number platform for Hitachi Yutaki."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

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

    register_key: str | None = None
    multiplier: float | None = None
    description: str | None = None


CIRCUIT_NUMBERS: Final[tuple[HitachiYutakiNumberEntityDescription, ...]] = (
    HitachiYutakiNumberEntityDescription(
        key="max_flow_temp_heating_otc",
        translation_key="max_flow_temp_heating_otc",
        description="Maximum heating water temperature used in outdoor temperature compensation (OTC) calculations",
        native_min_value=0,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="max_flow_temp_heating_otc",
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HitachiYutakiNumberEntityDescription(
        key="max_flow_temp_cooling_otc",
        translation_key="max_flow_temp_cooling_otc",
        description="Maximum cooling water temperature used in outdoor temperature compensation (OTC) calculations",
        native_min_value=0,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="max_flow_temp_cooling_otc",
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HitachiYutakiNumberEntityDescription(
        key="heat_eco_offset",
        translation_key="heat_eco_offset",
        description="Temperature offset applied in ECO mode for heating",
        native_min_value=1,
        native_max_value=10,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="heat_eco_offset",
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    HitachiYutakiNumberEntityDescription(
        key="cool_eco_offset",
        translation_key="cool_eco_offset",
        description="Temperature offset applied in ECO mode for cooling",
        native_min_value=1,
        native_max_value=10,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="cool_eco_offset",
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    HitachiYutakiNumberEntityDescription(
        key="target_temp",
        translation_key="target_temp",
        description="Target room temperature when using the thermostat function",
        native_min_value=5.0,
        native_max_value=35.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="target_temp",
        mode=NumberMode.BOX,
        multiplier=10,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        entity_registry_visible_default=False,
    ),
    HitachiYutakiNumberEntityDescription(
        key="current_temp",
        translation_key="current_temp",
        description="Measured room temperature for this circuit",
        native_min_value=0.0,
        native_max_value=50.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="current_temp",
        mode=NumberMode.BOX,
        multiplier=10,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        entity_registry_visible_default=False,
    ),
)

DHW_NUMBERS: Final[tuple[HitachiYutakiNumberEntityDescription, ...]] = (
    HitachiYutakiNumberEntityDescription(
        key="target_temp",
        translation_key="dhw_target_temperature",
        description="Target temperature for domestic hot water",
        native_min_value=30,
        native_max_value=60,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="target_temp",
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HitachiYutakiNumberEntityDescription(
        key="antilegionella_temp",
        translation_key="antilegionella_temp",
        description="Target temperature for anti-legionella treatment",
        native_min_value=60,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="antilegionella_temp",
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
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
        register_key="pool_target_temp",
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
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
        self.register_prefix = register_prefix
        self._register_key = (
            f"{register_prefix}_{description.register_key}"
            if register_prefix
            else description.register_key
        )
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = (
            f"{entry_id}_{coordinator.slave}_{register_prefix}_{description.key}"
            if register_prefix
            else f"{entry_id}_{coordinator.slave}_{description.key}"
        )
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        if self.coordinator.data is None or self._register_key is None:
            return None

        value = self.coordinator.data.get(self._register_key)
        if value is None:
            return None

        # Convert value if multiplier is set
        if self.entity_description.multiplier:
            return float(value) / self.entity_description.multiplier

        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self._register_key is None:
            return

        # Convert value if multiplier is set
        if self.entity_description.multiplier:
            value = value * self.entity_description.multiplier

        await self.coordinator.async_write_register(self._register_key, int(value))

    def set_native_value(self, value: float) -> None:
        """Set new value."""
        raise NotImplementedError
