"""Base binary sensor entity and description for Hitachi Yutaki."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import (
    DOMAIN,
)
from ..coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Hitachi Yutaki binary sensor entities."""

    key: str
    device_class: BinarySensorDeviceClass | None = None
    entity_category: EntityCategory | None = None
    icon: str | None = None
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True

    value_fn: Callable[[HitachiYutakiDataCoordinator], bool] | None = None
    condition: Callable[[HitachiYutakiDataCoordinator], bool] | None = None
    translation_key: str | None = None
    description: str | None = None


def _create_binary_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    descriptions: tuple[HitachiYutakiBinarySensorEntityDescription, ...],
    device_type: str,
) -> list[HitachiYutakiBinarySensor]:
    """Create binary sensors for a specific device type.

    Args:
        coordinator: The data coordinator
        entry_id: The config entry ID
        descriptions: Binary sensor descriptions to create
        device_type: Device type identifier (e.g., DEVICE_GATEWAY)

    Returns:
        List of created binary sensor entities

    """
    return [
        HitachiYutakiBinarySensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry_id}_{device_type}")},
            ),
        )
        for description in descriptions
        if description.condition is None or description.condition(coordinator)
    ]


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
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if (
            not self.coordinator.last_update_success
            or not self.entity_description.value_fn
        ):
            return None

        return self.entity_description.value_fn(self.coordinator)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success
