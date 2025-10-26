"""Control unit sensor descriptions and builders (outdoor + diagnostics)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory

from ...const import DEVICE_CONTROL_UNIT
from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_control_unit_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build control unit sensor entities (outdoor + diagnostics)."""
    descriptions = _build_control_unit_sensor_descriptions()
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT)


def _build_control_unit_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build control unit sensor descriptions."""
    return (
        # Outdoor sensors
        HitachiYutakiSensorEntityDescription(
            key="outdoor_temp",
            translation_key="outdoor_temp",
            description="Outdoor ambient temperature measurement",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            value_fn=lambda coordinator: coordinator.data.get("outdoor_temp"),
        ),
        # Diagnostics sensors (alarm, operation_state only - power_consumption moved to power/)
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
