"""Power sensor descriptions and builders (electrical consumption + cost)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.entity import EntityCategory

from ...const import CONF_ELECTRICITY_PRICE_ENTITY, DEVICE_CONTROL_UNIT
from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_power_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build power sensor entities (electrical consumption + cost)."""
    descriptions = _build_power_sensor_descriptions(coordinator)
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT)


def _build_power_sensor_descriptions(
    coordinator: HitachiYutakiDataCoordinator,
) -> tuple[HitachiYutakiSensorEntityDescription, ...]:
    """Build power sensor descriptions."""
    descriptions: list[HitachiYutakiSensorEntityDescription] = [
        HitachiYutakiSensorEntityDescription(
            key="power_consumption",
            translation_key="power_consumption",
            description="Total electrical energy consumed by the unit",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            value_fn=lambda c: c.data.get("electrical_energy_consumed"),
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ]

    # Electricity cost sensor — only when price entity is configured
    if coordinator.config_entry.data.get(CONF_ELECTRICITY_PRICE_ENTITY):
        currency = coordinator.hass.config.currency
        descriptions.append(
            HitachiYutakiSensorEntityDescription(
                key="electricity_cost",
                translation_key="electricity_cost",
                description="Cumulative electricity cost of the heat pump",
                device_class=SensorDeviceClass.MONETARY,
                state_class=SensorStateClass.TOTAL,
                native_unit_of_measurement=currency,
                value_fn=lambda c: c.data.get("electricity_cost"),
                attributes_fn=lambda c: {
                    "price_entity": c.config_entry.data.get(
                        CONF_ELECTRICITY_PRICE_ENTITY
                    ),
                    "current_price": c.data.get("_current_price"),
                },
            ),
        )

    return tuple(descriptions)
