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
    UnitOfTemperature,
    EntityCategory,
)
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
    DEVICE_POOL,
)
from .coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiNumberEntityDescription(NumberEntityDescription):
    """Class describing Hitachi Yutaki number entities."""

    register_key: str | None = None
    multiplier: float | None = None
    description: str | None = None


CIRCUIT_NUMBERS: Final[tuple[HitachiYutakiNumberEntityDescription, ...]] = (
    HitachiYutakiNumberEntityDescription(
        key="water_heating_temp_setting",
        translation_key="water_heating_temp_setting",
        description="Target water temperature when the temperature control mode is set to 'fix'",
        native_min_value=0,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="water_heating_temp_setting",
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HitachiYutakiNumberEntityDescription(
        key="water_cooling_temp_setting",
        translation_key="water_cooling_temp_setting",
        description="Target water temperature when the temperature control mode is set to 'fix'",
        native_min_value=0,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="water_cooling_temp_setting",
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
        mode=NumberMode.SLIDER,
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
        key="thermostat_temp",
        translation_key="thermostat_temp",
        description="Target room temperature when using the thermostat function",
        native_min_value=5.0,
        native_max_value=35.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="thermostat_temp",
        mode=NumberMode.BOX,
        multiplier=10,
    ),
)

DHW_NUMBERS: Final[tuple[HitachiYutakiNumberEntityDescription, ...]] = (
    HitachiYutakiNumberEntityDescription(
        key="temperature",
        translation_key="temperature",
        description="Target temperature for domestic hot water",
        native_min_value=0,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="temperature",
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    HitachiYutakiNumberEntityDescription(
        key="antilegionella_temp",
        translation_key="antilegionella_temp",
        description="Target temperature for anti-legionella treatment",
        native_min_value=0,
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
        key="temperature",
        translation_key="temperature",
        description="Target temperature for swimming pool water",
        native_min_value=0,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="temperature",
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
            if (
                "cool" in description.key
                and not coordinator.has_cooling_circuit1()
            ):
                continue
            # Skip thermostat temp if thermostat is not configured
            if (
                "thermostat" in description.key
                and not coordinator.data.get("circuit1_thermostat", 0)
            ):
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
            if (
                "cool" in description.key
                and not coordinator.has_cooling_circuit2()
            ):
                continue
            # Skip thermostat temp if thermostat is not configured
            if (
                "thermostat" in description.key
                and not coordinator.data.get("circuit2_thermostat", 0)
            ):
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
        self._attr_unique_id = f"{coordinator.slave}_{register_prefix}_{description.key}" if register_prefix else f"{coordinator.slave}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        if (
            self.coordinator.data is None
            or self._register_key is None
        ):
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
