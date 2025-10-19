"""Diagnostic sensor descriptions."""

from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.entity import EntityCategory

from .base import HitachiYutakiSensorEntityDescription

DIAGNOSTIC_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="power_consumption",
        translation_key="power_consumption",
        description="Total electrical energy consumed by the unit",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda coordinator: coordinator.data.get("power_consumption"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="alarm",
        translation_key="alarm",
        description="Current alarm",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        value_fn=lambda coordinator: coordinator.data.get("alarm_code"),
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-circle-outline",
    ),
    HitachiYutakiSensorEntityDescription(
        key="operation_state",
        translation_key="operation_state",
        description="Current operation state of the heat pump",
        value_fn=lambda coordinator: coordinator.data.get("operation_state"),
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:state-machine",
    ),
)
