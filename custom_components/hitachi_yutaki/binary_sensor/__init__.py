"""Binary sensor platform for Hitachi Yutaki integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import (
    DEVICE_CONTROL_UNIT,
    DEVICE_DHW,
    DEVICE_GATEWAY,
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_SECONDARY_COMPRESSOR,
    DOMAIN,
)
from ..coordinator import HitachiYutakiDataCoordinator
from .base import _create_binary_sensors
from .compressor import (
    PRIMARY_COMPRESSOR_BINARY_SENSORS,
    SECONDARY_COMPRESSOR_BINARY_SENSORS,
)
from .control_unit import CONTROL_UNIT_BINARY_SENSORS
from .dhw import DHW_BINARY_SENSORS
from .gateway import GATEWAY_BINARY_SENSORS
from .hydraulic import HYDRAULIC_BINARY_SENSORS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Add binary sensors by device type
    entities.extend(
        _create_binary_sensors(
            coordinator, entry.entry_id, GATEWAY_BINARY_SENSORS, DEVICE_GATEWAY
        )
    )
    entities.extend(
        _create_binary_sensors(
            coordinator,
            entry.entry_id,
            CONTROL_UNIT_BINARY_SENSORS,
            DEVICE_CONTROL_UNIT,
        )
    )
    entities.extend(
        _create_binary_sensors(
            coordinator, entry.entry_id, HYDRAULIC_BINARY_SENSORS, DEVICE_CONTROL_UNIT
        )
    )

    entities.extend(
        _create_binary_sensors(
            coordinator, entry.entry_id, DHW_BINARY_SENSORS, DEVICE_DHW
        )
    )

    entities.extend(
        _create_binary_sensors(
            coordinator,
            entry.entry_id,
            PRIMARY_COMPRESSOR_BINARY_SENSORS,
            DEVICE_PRIMARY_COMPRESSOR,
        )
    )
    entities.extend(
        _create_binary_sensors(
            coordinator,
            entry.entry_id,
            SECONDARY_COMPRESSOR_BINARY_SENSORS,
            DEVICE_SECONDARY_COMPRESSOR,
        )
    )

    async_add_entities(entities)
