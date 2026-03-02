"""Water heater platform for Hitachi Yutaki."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HitachiYutakiConfigEntry

# Import builder from domain entity
from .entities.dhw import build_dhw_water_heater


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HitachiYutakiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the water heater."""
    coordinator = entry.runtime_data

    entities = []

    # Build DHW water heater if configured
    water_heater = build_dhw_water_heater(coordinator, entry.entry_id)
    if water_heater:
        entities.append(water_heater)

    async_add_entities(entities)
