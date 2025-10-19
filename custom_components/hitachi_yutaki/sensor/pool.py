"""Pool sensor descriptions."""

from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature

from .base import HitachiYutakiSensorEntityDescription

POOL_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="pool_current_temp",
        translation_key="pool_current_temperature",
        description="Current temperature of the pool",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coordinator: coordinator.data.get("pool_current_temp"),
    ),
)
