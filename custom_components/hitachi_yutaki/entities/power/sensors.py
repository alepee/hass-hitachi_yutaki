"""Power sensor descriptions and builders (electrical consumption)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.entity import EntityCategory

from ...const import DEVICE_CONTROL_UNIT
from ..base.sensor import HitachiYutakiSensor, HitachiYutakiSensorEntityDescription

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_power_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build power sensor entities (electrical consumption)."""
    from ..base.sensor import _create_sensors

    descriptions = _build_power_sensor_descriptions()
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT)


def _build_power_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build power sensor descriptions."""
    return (
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
    )
