"""Hydraulic binary sensor descriptions."""

from __future__ import annotations

from typing import Final

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from .base import HitachiYutakiBinarySensorEntityDescription

HYDRAULIC_BINARY_SENSORS: Final[
    tuple[HitachiYutakiBinarySensorEntityDescription, ...]
] = (
    HitachiYutakiBinarySensorEntityDescription(
        key="pump1",
        translation_key="pump1",
        icon="mdi:pump",
        description="Indicates if water pump 1 is running",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.api_client.is_pump1_running,
        entity_registry_enabled_default=False,
    ),
    HitachiYutakiBinarySensorEntityDescription(
        key="pump2",
        translation_key="pump2",
        icon="mdi:pump",
        description="Indicates if water pump 2 is running",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.api_client.is_pump2_running,
        entity_registry_enabled_default=False,
    ),
    HitachiYutakiBinarySensorEntityDescription(
        key="pump3",
        translation_key="pump3",
        icon="mdi:pump",
        description="Indicates if water pump 3 is running",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.api_client.is_pump3_running,
        entity_registry_enabled_default=False,
    ),
)
