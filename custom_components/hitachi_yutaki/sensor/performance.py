"""Performance sensor descriptions (COP)."""

from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import SensorStateClass
from homeassistant.helpers.entity import EntityCategory

from .base import HitachiYutakiSensorEntityDescription

PERFORMANCE_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="cop_heating",
        translation_key="cop_heating",
        description="Coefficient of Performance for Space Heating",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:heat-pump",
        condition=lambda c: c.has_circuit1_heating() or c.has_circuit2_heating(),
    ),
    HitachiYutakiSensorEntityDescription(
        key="cop_cooling",
        translation_key="cop_cooling",
        description="Coefficient of Performance for Space Cooling",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:heat-pump-outline",
        condition=lambda c: c.has_circuit1_cooling() or c.has_circuit2_cooling(),
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
    ),
)
