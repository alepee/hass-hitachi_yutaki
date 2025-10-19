"""Compressor binary sensor descriptions."""

from __future__ import annotations

from typing import Final

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from .base import HitachiYutakiBinarySensorEntityDescription

PRIMARY_COMPRESSOR_BINARY_SENSORS: Final[
    tuple[HitachiYutakiBinarySensorEntityDescription, ...]
] = (
    HitachiYutakiBinarySensorEntityDescription(
        key="compressor_running",
        translation_key="compressor_running",
        description="Indicates if the primary compressor is running",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:engine",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.api_client.is_primary_compressor_running,
    ),
)

SECONDARY_COMPRESSOR_BINARY_SENSORS: Final[
    tuple[HitachiYutakiBinarySensorEntityDescription, ...]
] = (
    HitachiYutakiBinarySensorEntityDescription(
        key="secondary_compressor_running",
        translation_key="secondary_compressor_running",
        description="Indicates if the secondary compressor is running",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:engine",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.api_client.is_secondary_compressor_running,
        condition=lambda c: c.profile.supports_secondary_compressor,
    ),
)
