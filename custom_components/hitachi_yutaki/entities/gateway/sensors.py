"""Gateway sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from ...const import DEVICE_GATEWAY
from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_gateway_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build gateway sensor entities."""
    descriptions = _build_gateway_sensor_descriptions()
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_GATEWAY)


def _build_gateway_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build gateway sensor descriptions."""
    return (
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
