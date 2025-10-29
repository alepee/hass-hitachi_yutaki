"""Binary sensor platform for Hitachi Yutaki integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_SECONDARY_COMPRESSOR,
    DOMAIN,
)
from .coordinator import HitachiYutakiDataCoordinator

# Import builders from domain entities
from .entities.compressor import build_compressor_binary_sensors
from .entities.control_unit import build_control_unit_binary_sensors
from .entities.dhw import build_dhw_binary_sensors
from .entities.gateway import build_gateway_binary_sensors
from .entities.hydraulic import build_hydraulic_binary_sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Gateway binary sensors
    entities.extend(build_gateway_binary_sensors(coordinator, entry.entry_id))

    # Control unit binary sensors
    entities.extend(build_control_unit_binary_sensors(coordinator, entry.entry_id))

    # Hydraulic binary sensors
    entities.extend(build_hydraulic_binary_sensors(coordinator, entry.entry_id))

    # DHW binary sensors
    if coordinator.has_dhw():
        entities.extend(build_dhw_binary_sensors(coordinator, entry.entry_id))

    # Compressor binary sensors
    entities.extend(
        build_compressor_binary_sensors(
            coordinator,
            entry.entry_id,
            compressor_id=1,
            device_type=DEVICE_PRIMARY_COMPRESSOR,
        )
    )
    entities.extend(
        build_compressor_binary_sensors(
            coordinator,
            entry.entry_id,
            compressor_id=2,
            device_type=DEVICE_SECONDARY_COMPRESSOR,
        )
    )

    async_add_entities(entities)
