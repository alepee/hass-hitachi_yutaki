"""Climate platform for Hitachi Yutaki."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from . import HitachiYutakiConfigEntry
from .const import (
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
)

# Import builder from domain entity
from .entities.circuit import build_circuit_climate

SERVICE_SET_ROOM_TEMPERATURE = "set_room_temperature"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HitachiYutakiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate entities."""
    coordinator = entry.runtime_data

    entities = []

    # Build climate entities for each circuit
    climate1 = build_circuit_climate(
        coordinator, entry.entry_id, circuit_id=1, device_type=DEVICE_CIRCUIT_1
    )
    if climate1:
        entities.append(climate1)

    climate2 = build_circuit_climate(
        coordinator, entry.entry_id, circuit_id=2, device_type=DEVICE_CIRCUIT_2
    )
    if climate2:
        entities.append(climate2)

    async_add_entities(entities)

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_ROOM_TEMPERATURE,
        {
            vol.Required(ATTR_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=50.0)
            ),
        },
        "async_set_room_temperature",
    )
