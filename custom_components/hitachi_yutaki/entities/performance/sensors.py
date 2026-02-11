"""Performance sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorStateClass
from homeassistant.helpers.entity import EntityCategory

from ...const import (
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    DEVICE_CONTROL_UNIT,
)
from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_performance_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build performance sensor entities."""
    descriptions = _build_performance_sensor_descriptions()
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT)


def _build_performance_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build performance sensor descriptions."""
    return (
        HitachiYutakiSensorEntityDescription(
            key="cop_heating",
            translation_key="cop_heating",
            description="Coefficient of Performance for Space Heating",
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:heat-pump",
            condition=lambda c: c.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING)
            or c.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING),
            sensor_class="cop",
        ),
        HitachiYutakiSensorEntityDescription(
            key="cop_cooling",
            translation_key="cop_cooling",
            description="Coefficient of Performance for Space Cooling",
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:heat-pump-outline",
            condition=lambda c: c.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING)
            or c.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING),
            sensor_class="cop",
        ),
        HitachiYutakiSensorEntityDescription(
            key="cop_dhw",
            translation_key="cop_dhw",
            description="Coefficient of Performance for Domestic Hot Water",
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:water-boiler",
            condition=lambda c: c.has_dhw(),
            sensor_class="cop",
        ),
        HitachiYutakiSensorEntityDescription(
            key="cop_pool",
            translation_key="cop_pool",
            description="Coefficient of Performance for Pool Heating",
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:pool",
            condition=lambda c: c.has_pool(),
            sensor_class="cop",
        ),
    )
