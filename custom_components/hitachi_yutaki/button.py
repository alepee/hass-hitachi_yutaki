"""Button platform for Hitachi Yutaki integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HitachiYutakiConfigEntry

# Import builders from domain entities
from .entities.dhw import build_dhw_buttons


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HitachiYutakiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the buttons."""
    coordinator = entry.runtime_data

    entities = []

    # DHW buttons
    if coordinator.has_dhw():
        entities.extend(build_dhw_buttons(coordinator, entry.entry_id))

    async_add_entities(entities)
