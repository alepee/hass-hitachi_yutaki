"""Switch platform for Hitachi Yutaki integration."""

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
    DOMAIN,
)
from .coordinator import HitachiYutakiDataCoordinator

# Import builders from domain entities
from .entities.circuit import build_circuit_switches
from .entities.control_unit import build_control_unit_switches
from .entities.dhw import build_dhw_switches
from .entities.pool import build_pool_switches


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switches."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Control unit switches
    entities.extend(build_control_unit_switches(coordinator, entry.entry_id))

    # Circuit switches (dynamic based on configuration)
    # Circuit 1 switches
    if coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING):
        entities.extend(
            build_circuit_switches(
                coordinator,
                entry.entry_id,
                CIRCUIT_PRIMARY_ID,
                DEVICE_CIRCUIT_1,
            )
        )

    # Circuit 2 switches
    if coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING):
        entities.extend(
            build_circuit_switches(
                coordinator,
                entry.entry_id,
                CIRCUIT_SECONDARY_ID,
                DEVICE_CIRCUIT_2,
            )
        )

    # DHW switches
    if coordinator.has_dhw():
        entities.extend(build_dhw_switches(coordinator, entry.entry_id))

    # Pool switches
    if coordinator.has_pool():
        entities.extend(build_pool_switches(coordinator, entry.entry_id))

    async_add_entities(entities)
