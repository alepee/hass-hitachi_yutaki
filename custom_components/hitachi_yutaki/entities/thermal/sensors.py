"""Thermal energy sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.entity import EntityCategory

from ...const import DEVICE_CONTROL_UNIT
from ..base.sensor import HitachiYutakiSensor, HitachiYutakiSensorEntityDescription

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_thermal_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build thermal energy sensor entities."""
    from ..base.sensor import _create_sensors

    descriptions = _build_thermal_sensor_descriptions()
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT)


def _build_thermal_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build thermal energy sensor descriptions."""
    return (
        HitachiYutakiSensorEntityDescription(
            key="thermal_power",
            translation_key="thermal_power",
            description="Current thermal power output",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:heat-wave",
        ),
        HitachiYutakiSensorEntityDescription(
            key="daily_thermal_energy",
            translation_key="daily_thermal_energy",
            description="Daily thermal energy production (resets at midnight)",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:heat-wave",
        ),
        HitachiYutakiSensorEntityDescription(
            key="total_thermal_energy",
            translation_key="total_thermal_energy",
            description="Total thermal energy production",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:heat-wave",
        ),
    )
