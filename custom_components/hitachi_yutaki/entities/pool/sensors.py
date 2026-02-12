"""Pool sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature

from ...const import DEVICE_POOL
from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_pool_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build pool sensor entities."""
    descriptions = _build_pool_sensor_descriptions()
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_POOL)


def _build_pool_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build pool sensor descriptions."""
    return (
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
