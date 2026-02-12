"""Select platform for Hitachi Yutaki integration."""

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
from .entities.circuit import build_circuit_selects
from .entities.control_unit import build_control_unit_selects


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the selects."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Control unit selects
    entities.extend(build_control_unit_selects(coordinator, entry.entry_id))

    # Circuit selects (dynamic based on configuration)
    # Circuit 1 selects
    if coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING):
        entities.extend(
            build_circuit_selects(
                coordinator,
                entry.entry_id,
                circuit_id=CIRCUIT_PRIMARY_ID,
                device_type=DEVICE_CIRCUIT_1,
            )
        )

    # Circuit 2 selects
    if coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING):
        entities.extend(
            build_circuit_selects(
                coordinator,
                entry.entry_id,
                circuit_id=CIRCUIT_SECONDARY_ID,
                device_type=DEVICE_CIRCUIT_2,
            )
        )

    async_add_entities(entities)
