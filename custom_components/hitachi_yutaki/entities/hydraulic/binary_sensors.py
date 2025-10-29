"""Hydraulic binary sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from ...const import DEVICE_CONTROL_UNIT
from ..base.binary_sensor import (
    HitachiYutakiBinarySensor,
    HitachiYutakiBinarySensorEntityDescription,
    _create_binary_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_hydraulic_binary_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiBinarySensor]:
    """Build hydraulic binary sensor entities."""
    descriptions = _build_hydraulic_binary_sensor_descriptions()
    return _create_binary_sensors(
        coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT
    )


def _build_hydraulic_binary_sensor_descriptions() -> tuple[
    HitachiYutakiBinarySensorEntityDescription, ...
]:
    """Build hydraulic binary sensor descriptions."""
    return (
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
