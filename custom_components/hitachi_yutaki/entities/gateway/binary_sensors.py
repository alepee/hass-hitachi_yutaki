"""Gateway binary sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from ...const import DEVICE_GATEWAY
from ..base.binary_sensor import (
    HitachiYutakiBinarySensor,
    HitachiYutakiBinarySensorEntityDescription,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_gateway_binary_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiBinarySensor]:
    """Build gateway binary sensor entities."""
    from ..base.binary_sensor import _create_binary_sensors

    descriptions = _build_gateway_binary_sensor_descriptions()
    return _create_binary_sensors(coordinator, entry_id, descriptions, DEVICE_GATEWAY)


def _build_gateway_binary_sensor_descriptions() -> tuple[
    HitachiYutakiBinarySensorEntityDescription, ...
]:
    """Build gateway binary sensor descriptions."""
    return (
        HitachiYutakiBinarySensorEntityDescription(
            key="connectivity",
            translation_key="connectivity",
            description="Indicates if the gateway is connected and responding",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda coordinator: coordinator.last_update_success,
        ),
    )
