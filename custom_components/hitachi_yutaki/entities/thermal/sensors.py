"""Thermal energy sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.entity import EntityCategory

from ...const import CIRCUIT_MODE_COOLING, CIRCUIT_PRIMARY_ID, DEVICE_CONTROL_UNIT
from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_thermal_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build thermal energy sensor entities."""
    descriptions = _build_thermal_sensor_descriptions(coordinator)
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT)


def _build_thermal_sensor_descriptions(
    coordinator: HitachiYutakiDataCoordinator,
) -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build thermal energy sensor descriptions."""
    has_cooling = coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING)

    # New explicit heating sensors (always created)
    sensors = [
        HitachiYutakiSensorEntityDescription(
            key="thermal_power_heating",
            translation_key="thermal_power_heating",
            description="Current thermal heating power output",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:heat-wave",
        ),
        HitachiYutakiSensorEntityDescription(
            key="thermal_energy_heating_daily",
            translation_key="thermal_energy_heating_daily",
            description="Daily thermal heating energy production (resets at midnight)",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:heat-wave",
        ),
        HitachiYutakiSensorEntityDescription(
            key="thermal_energy_heating_total",
            translation_key="thermal_energy_heating_total",
            description="Total thermal heating energy production",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:heat-wave",
        ),
    ]

    # Cooling sensors (only if cooling circuit exists)
    if has_cooling:
        sensors.extend([
            HitachiYutakiSensorEntityDescription(
                key="thermal_power_cooling",
                translation_key="thermal_power_cooling",
                description="Current thermal cooling power output",
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="kW",
                entity_category=EntityCategory.DIAGNOSTIC,
                icon="mdi:snowflake",
            ),
            HitachiYutakiSensorEntityDescription(
                key="thermal_energy_cooling_daily",
                translation_key="thermal_energy_cooling_daily",
                description="Daily thermal cooling energy production (resets at midnight)",
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                entity_category=EntityCategory.DIAGNOSTIC,
                icon="mdi:snowflake",
            ),
            HitachiYutakiSensorEntityDescription(
                key="thermal_energy_cooling_total",
                translation_key="thermal_energy_cooling_total",
                description="Total thermal cooling energy production",
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                entity_category=EntityCategory.DIAGNOSTIC,
                icon="mdi:snowflake",
            ),
        ])

    return tuple(sensors)
