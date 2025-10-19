"""Outdoor sensor descriptions."""

from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature

from .base import HitachiYutakiSensorEntityDescription

OUTDOOR_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="outdoor_temp",
        translation_key="outdoor_temp",
        description="Outdoor ambient temperature measurement",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coordinator: coordinator.data.get("outdoor_temp"),
    ),
)
