"""Binary sensor platform for Hitachi Yutaki."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import (
    DOMAIN,
    MASK_DEFROST,
    MASK_SOLAR,
    MASK_PUMP1,
    MASK_PUMP2,
    MASK_PUMP3,
    MASK_COMPRESSOR,
    MASK_BOILER,
    MASK_DHW_HEATER,
    MASK_SPACE_HEATER,
    MASK_SMART_FUNCTION,
    DEVICE_CONTROL_UNIT,
    DEVICE_GATEWAY,
)
from .coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Hitachi Yutaki binary sensor entities."""
    register_key: str | None = None
    mask: int | None = None
    description: str | None = None


GATEWAY_BINARY_SENSORS: Final[tuple[HitachiYutakiBinarySensorEntityDescription, ...]] = (
    HitachiYutakiBinarySensorEntityDescription(
        key="connectivity",
        translation_key="connectivity",
        description="Indicates if the gateway is connected and responding",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="is_available",
    ),
)

CONTROL_UNIT_BINARY_SENSORS: Final[tuple[HitachiYutakiBinarySensorEntityDescription, ...]] = (
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
    ),
    HitachiYutakiBinarySensorEntityDescription(
        key="space_heater",
        translation_key="space_heater",
        description="Indicates if the space heating electric heater is active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        register_key="system_status",
        mask=MASK_SPACE_HEATER,
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

    # Add gateway binary sensors
    entities.extend(
        HitachiYutakiBinarySensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_GATEWAY}")},
            ),
        )
        for description in GATEWAY_BINARY_SENSORS
    )

    # Add control unit binary sensors
    entities.extend(
        HitachiYutakiBinarySensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
            ),
        )
        for description in CONTROL_UNIT_BINARY_SENSORS
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
        self._attr_unique_id = f"{coordinator.slave}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.register_key == "is_available":
            return self.coordinator.data.get("is_available", False)

        if self.entity_description.register_key is None or self.entity_description.mask is None:
            return None

        register_value = self.coordinator.data.get(self.entity_description.register_key)
        if register_value is None:
            return None

        return bool(register_value & self.entity_description.mask)
