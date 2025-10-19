"""Sensor platform for Hitachi Yutaki integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import (
    DEVICE_CONTROL_UNIT,
    DEVICE_DHW,
    DEVICE_GATEWAY,
    DEVICE_POOL,
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_SECONDARY_COMPRESSOR,
    DOMAIN,
)
from ..coordinator import HitachiYutakiDataCoordinator
from .base import _create_sensors
from .compressor import PRIMARY_COMPRESSOR_SENSORS, SECONDARY_COMPRESSOR_SENSORS
from .dhw import DHW_SENSORS
from .diagnostics import DIAGNOSTIC_SENSORS
from .gateway import GATEWAY_SENSORS
from .hydraulic import HYDRAULIC_SENSORS
from .outdoor import OUTDOOR_SENSORS
from .performance import PERFORMANCE_SENSORS
from .pool import POOL_SENSORS
from .thermal import THERMAL_ENERGY_SENSORS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Add sensors by device type
    entities.extend(
        _create_sensors(coordinator, entry.entry_id, GATEWAY_SENSORS, DEVICE_GATEWAY)
    )
    entities.extend(
        _create_sensors(
            coordinator, entry.entry_id, OUTDOOR_SENSORS, DEVICE_CONTROL_UNIT
        )
    )
    entities.extend(
        _create_sensors(
            coordinator, entry.entry_id, HYDRAULIC_SENSORS, DEVICE_CONTROL_UNIT
        )
    )

    if coordinator.has_dhw():
        entities.extend(
            _create_sensors(coordinator, entry.entry_id, DHW_SENSORS, DEVICE_DHW)
        )

    if coordinator.has_pool():
        entities.extend(
            _create_sensors(coordinator, entry.entry_id, POOL_SENSORS, DEVICE_POOL)
        )

    entities.extend(
        _create_sensors(
            coordinator, entry.entry_id, DIAGNOSTIC_SENSORS, DEVICE_CONTROL_UNIT
        )
    )
    entities.extend(
        _create_sensors(
            coordinator,
            entry.entry_id,
            PRIMARY_COMPRESSOR_SENSORS,
            DEVICE_PRIMARY_COMPRESSOR,
        )
    )
    entities.extend(
        _create_sensors(
            coordinator,
            entry.entry_id,
            SECONDARY_COMPRESSOR_SENSORS,
            DEVICE_SECONDARY_COMPRESSOR,
        )
    )
    entities.extend(
        _create_sensors(
            coordinator, entry.entry_id, PERFORMANCE_SENSORS, DEVICE_CONTROL_UNIT
        )
    )
    entities.extend(
        _create_sensors(
            coordinator, entry.entry_id, THERMAL_ENERGY_SENSORS, DEVICE_CONTROL_UNIT
        )
    )

    # Register entities with coordinator
    coordinator.entities.extend(entities)

    async_add_entities(entities)
