"""Gateway binary sensor descriptions."""

from __future__ import annotations

from typing import Final

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from .base import HitachiYutakiBinarySensorEntityDescription

GATEWAY_BINARY_SENSORS: Final[
    tuple[HitachiYutakiBinarySensorEntityDescription, ...]
] = (
    HitachiYutakiBinarySensorEntityDescription(
        key="connectivity",
        translation_key="connectivity",
        description="Indicates if the gateway is connected and responding",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.last_update_success,
    ),
)
