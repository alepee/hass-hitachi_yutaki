"""Binary sensor platform for Hitachi Yutaki."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_CONTROL_UNIT,
    DEVICE_DHW,
    DEVICE_GATEWAY,
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_SECONDARY_COMPRESSOR,
    DOMAIN,
    MASK_BOILER,
    MASK_COMPRESSOR,
    MASK_DEFROST,
    MASK_DHW_HEATER,
    MASK_PUMP1,
    MASK_PUMP2,
    MASK_PUMP3,
    MASK_SMART_FUNCTION,
    MASK_SOLAR,
    MASK_SPACE_HEATER,
)
from .coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Hitachi Yutaki binary sensor entities."""

    key: str
    device_class: BinarySensorDeviceClass | None = None
    entity_category: EntityCategory | None = None
    icon: str | None = None
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True

    register_key: str | None = None
    mask: int | None = None
    value_fn: Callable[[Any, HitachiYutakiDataCoordinator], bool] | None = None
    condition: Callable[[HitachiYutakiDataCoordinator], bool] | None = None
    translation_key: str | None = None
    description: str | None = None


GATEWAY_BINARY_SENSORS: Final[
    tuple[HitachiYutakiBinarySensorEntityDescription, ...]
] = (
    HitachiYutakiBinarySensorEntityDescription(
        key="connectivity",
        translation_key="connectivity",
        description="Indicates if the gateway is connected and responding",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="is_available",
        value_fn=lambda value, _: bool(value),
    ),
)

CONTROL_UNIT_BINARY_SENSORS: Final[
    tuple[HitachiYutakiBinarySensorEntityDescription, ...]
] = (
    HitachiYutakiBinarySensorEntityDescription(
        key="defrost",
        translation_key="defrost",
        icon="mdi:snowflake",
        description="Indicates if the unit is currently in defrost mode",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="system_status",
        mask=MASK_DEFROST,
    ),
    HitachiYutakiBinarySensorEntityDescription(
        key="solar",
        translation_key="solar",
        icon="mdi:solar-power",
        description="Indicates if the solar system is active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="system_status",
        mask=MASK_SOLAR,
        entity_registry_enabled_default=False,
    ),
    HitachiYutakiBinarySensorEntityDescription(
        key="pump1",
        translation_key="pump1",
        icon="mdi:pump",
        description="Indicates if water pump 1 is running",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="system_status",
        mask=MASK_PUMP1,
        entity_registry_enabled_default=False,
    ),
    HitachiYutakiBinarySensorEntityDescription(
        key="pump2",
        translation_key="pump2",
        icon="mdi:pump",
        description="Indicates if water pump 2 is running",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="system_status",
        mask=MASK_PUMP2,
        entity_registry_enabled_default=False,
    ),
    HitachiYutakiBinarySensorEntityDescription(
        key="pump3",
        translation_key="pump3",
        icon="mdi:pump",
        description="Indicates if water pump 3 is running",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="system_status",
        mask=MASK_PUMP3,
        entity_registry_enabled_default=False,
    ),
    HitachiYutakiBinarySensorEntityDescription(
        key="compressor",
        translation_key="compressor",
        icon="mdi:heat-pump",
        description="Indicates if the compressor is running",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="system_status",
        mask=MASK_COMPRESSOR,
    ),
    HitachiYutakiBinarySensorEntityDescription(
        key="boiler",
        translation_key="boiler",
        icon="mdi:resistor",
        description="Indicates if the backup boiler is active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="system_status",
        mask=MASK_BOILER,
        condition=lambda c: c.is_s80_model() is False,
    ),
    HitachiYutakiBinarySensorEntityDescription(
        key="dhw_heater",
        translation_key="dhw_heater",
        icon="mdi:water-boiler",
        description="Indicates if the DHW electric heater is active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="system_status",
        mask=MASK_DHW_HEATER,
        condition=lambda c: c.has_dhw(),
    ),
    HitachiYutakiBinarySensorEntityDescription(
        key="space_heater",
        translation_key="space_heater",
        description="Indicates if the space heating electric heater is active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="system_status",
        mask=MASK_SPACE_HEATER,
        entity_registry_enabled_default=False,
    ),
    HitachiYutakiBinarySensorEntityDescription(
        key="smart_function",
        translation_key="smart_function",
        icon="mdi:home-automation",
        description="Indicates if the smart grid function is active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="system_status",
        mask=MASK_SMART_FUNCTION,
        entity_registry_enabled_default=False,
    ),
)

PRIMARY_COMPRESSOR_BINARY_SENSORS: Final[
    tuple[HitachiYutakiBinarySensorEntityDescription, ...]
] = (
    HitachiYutakiBinarySensorEntityDescription(
        key="compressor_running",
        translation_key="compressor_running",
        description="Indicates if the primary compressor is running",
        device_class=BinarySensorDeviceClass.RUNNING,
        register_key="compressor_frequency",
        icon="mdi:engine",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value, _: value is not None and value > 0,
    ),
)

SECONDARY_COMPRESSOR_BINARY_SENSORS: Final[
    tuple[HitachiYutakiBinarySensorEntityDescription, ...]
] = (
    HitachiYutakiBinarySensorEntityDescription(
        key="r134a_compressor_running",
        translation_key="r134a_compressor_running",
        description="Indicates if the R134a compressor is running",
        device_class=BinarySensorDeviceClass.RUNNING,
        register_key="r134a_compressor_frequency",
        icon="mdi:engine",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value, coordinator: value is not None and value > 0,
        condition=lambda c: c.is_s80_model(),
    ),
)

DHW_BINARY_SENSORS: Final[tuple[HitachiYutakiBinarySensorEntityDescription, ...]] = (
    HitachiYutakiBinarySensorEntityDescription(
        key="antilegionella_cycle",
        translation_key="antilegionella_cycle",
        icon="mdi:biohazard",
        description="Indicates if an anti-legionella cycle is currently running",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="dhw_antilegionella_status",
        value_fn=lambda value, _: value == 1,
        condition=lambda c: c.has_dhw(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[HitachiYutakiBinarySensor] = []

    # Add gateway binary sensors (always added)
    entities.extend(
        HitachiYutakiBinarySensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_GATEWAY}")},
            ),
        )
        for description in GATEWAY_BINARY_SENSORS
        if description.condition is None or description.condition(coordinator)
    )

    # Add control unit binary sensors based on configuration
    entities.extend(
        HitachiYutakiBinarySensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
            ),
        )
        for description in CONTROL_UNIT_BINARY_SENSORS
        if description.condition is None or description.condition(coordinator)
    )

    # Add primary compressor binary sensors
    entities.extend(
        HitachiYutakiBinarySensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_PRIMARY_COMPRESSOR}")},
            ),
        )
        for description in PRIMARY_COMPRESSOR_BINARY_SENSORS
        if description.condition is None or description.condition(coordinator)
    )

    # Add secondary compressor binary sensors
    entities.extend(
        HitachiYutakiBinarySensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={
                    (DOMAIN, f"{entry.entry_id}_{DEVICE_SECONDARY_COMPRESSOR}")
                },
            ),
        )
        for description in SECONDARY_COMPRESSOR_BINARY_SENSORS
        if description.condition is None or description.condition(coordinator)
    )

    # Add DHW binary sensors if configured
    entities.extend(
        HitachiYutakiBinarySensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DHW}")},
            ),
        )
        for description in DHW_BINARY_SENSORS
        if description.condition is None or description.condition(coordinator)
    )

    async_add_entities(entities)


class HitachiYutakiBinarySensor(
    CoordinatorEntity[HitachiYutakiDataCoordinator], BinarySensorEntity
):
    """Representation of a Hitachi Yutaki Binary Sensor."""

    entity_description: HitachiYutakiBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiBinarySensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{coordinator.slave}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if (
            self.coordinator.data is None
            or self.entity_description.register_key is None
            or not self.coordinator.last_update_success
        ):
            return None

        value = self.coordinator.data.get(self.entity_description.register_key)
        if value is None:
            return None

        # Use value_fn if provided
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(value, self.coordinator)

        # Otherwise use mask
        if self.entity_description.mask is not None:
            return bool(value & self.entity_description.mask)

        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success
