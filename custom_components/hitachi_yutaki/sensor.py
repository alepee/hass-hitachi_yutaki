"""Sensor platform for Hitachi Yutaki integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_SECONDARY_COMPRESSOR,
    DOMAIN,
)
from .coordinator import HitachiYutakiDataCoordinator

# Import builders from domain entities
from .entities.circuit import build_circuit_sensors
from .entities.compressor import build_compressor_sensors
from .entities.control_unit import build_control_unit_sensors
from .entities.dhw import build_dhw_sensors
from .entities.gateway import build_gateway_sensors
from .entities.hydraulic import build_hydraulic_sensors
from .entities.performance import build_performance_sensors
from .entities.pool import build_pool_sensors
from .entities.power import build_power_sensors
from .entities.thermal import build_thermal_sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Gateway sensors
    entities.extend(build_gateway_sensors(coordinator, entry.entry_id))

    # Control unit sensors (outdoor + diagnostics)
    entities.extend(build_control_unit_sensors(coordinator, entry.entry_id))

    # Hydraulic sensors
    entities.extend(build_hydraulic_sensors(coordinator, entry.entry_id))

    # Circuit sensors (dynamic based on configuration)
    # Circuit 1 sensors
    if coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING):
        entities.extend(
            build_circuit_sensors(
                coordinator,
                entry.entry_id,
                CIRCUIT_PRIMARY_ID,
                DEVICE_CIRCUIT_1,
            )
        )

    # Circuit 2 sensors
    if coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING):
        entities.extend(
            build_circuit_sensors(
                coordinator,
                entry.entry_id,
                CIRCUIT_SECONDARY_ID,
                DEVICE_CIRCUIT_2,
            )
        )

    # DHW sensors
    if coordinator.has_dhw():
        entities.extend(build_dhw_sensors(coordinator, entry.entry_id))

    # Pool sensors
    if coordinator.has_pool():
        entities.extend(build_pool_sensors(coordinator, entry.entry_id))

    # Compressor sensors
    entities.extend(
        build_compressor_sensors(
            coordinator,
            entry.entry_id,
            compressor_id=1,
            device_type=DEVICE_PRIMARY_COMPRESSOR,
        )
    )
    entities.extend(
        build_compressor_sensors(
            coordinator,
            entry.entry_id,
            compressor_id=2,
            device_type=DEVICE_SECONDARY_COMPRESSOR,
        )
    )

    # Performance sensors (COP)
    entities.extend(build_performance_sensors(coordinator, entry.entry_id))

    # Thermal sensors
    entities.extend(build_thermal_sensors(coordinator, entry.entry_id))

    # Power sensors (electrical consumption)
    entities.extend(build_power_sensors(coordinator, entry.entry_id))

    async_add_entities(entities)
