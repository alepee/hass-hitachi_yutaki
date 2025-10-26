"""Compressor binary sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.hitachi_yutaki.const import DEVICE_TYPES
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from ..base.binary_sensor import (
    HitachiYutakiBinarySensor,
    HitachiYutakiBinarySensorEntityDescription,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_compressor_binary_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    compressor_id: int,
    device_type: DEVICE_TYPES,
) -> list[HitachiYutakiBinarySensor]:
    """Build compressor binary sensor entities."""
    from ..base.binary_sensor import _create_binary_sensors

    descriptions = _build_compressor_binary_sensor_descriptions(compressor_id)
    return _create_binary_sensors(coordinator, entry_id, descriptions, device_type)


def _build_compressor_binary_sensor_descriptions(
    compressor_id: int,
) -> tuple[HitachiYutakiBinarySensorEntityDescription, ...]:
    """Build compressor binary sensor descriptions."""
    if compressor_id == 1:
        # Primary compressor
        return (
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
    else:
        # Secondary compressor
        return (
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
