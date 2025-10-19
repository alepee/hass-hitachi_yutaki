"""Gateway sensor descriptions."""

from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from .base import HitachiYutakiSensorEntityDescription

GATEWAY_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="system_state",
        translation_key="system_state",
        description="System state",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:state-machine",
        value_fn=lambda coordinator: coordinator.data.get("system_state"),
    ),
)
