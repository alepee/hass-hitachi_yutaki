"""Hydraulic sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfVolumeFlowRate
from homeassistant.helpers.entity import EntityCategory

from ...const import DEVICE_CONTROL_UNIT
from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_hydraulic_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build hydraulic sensor entities."""
    descriptions = _build_hydraulic_sensor_descriptions()
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT)


def _build_hydraulic_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build hydraulic sensor descriptions."""
    return (
        HitachiYutakiSensorEntityDescription(
            key="water_inlet_temp",
            translation_key="water_inlet_temp",
            description="Water inlet temperature measurement",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            value_fn=lambda coordinator: coordinator.data.get("water_inlet_temp"),
        ),
        HitachiYutakiSensorEntityDescription(
            key="water_outlet_temp",
            translation_key="water_outlet_temp",
            description="Water outlet temperature measurement",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            value_fn=lambda coordinator: coordinator.data.get("water_outlet_temp"),
        ),
        HitachiYutakiSensorEntityDescription(
            key="water_target_temp",
            translation_key="water_target_temp",
            description="Target water temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            value_fn=lambda coordinator: coordinator.data.get("water_target_temp"),
        ),
        HitachiYutakiSensorEntityDescription(
            key="water_flow",
            translation_key="water_flow",
            description="Current water flow rate through the system",
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            value_fn=lambda coordinator: coordinator.data.get("water_flow"),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        HitachiYutakiSensorEntityDescription(
            key="pump_speed",
            translation_key="pump_speed",
            description="Current speed of the water circulation pump",
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
            value_fn=lambda coordinator: coordinator.data.get("pump_speed"),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    )
