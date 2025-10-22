"""Number platform for Hitachi Yutaki integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import (
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_DHW,
    DEVICE_POOL,
    DOMAIN,
)
from ..coordinator import HitachiYutakiDataCoordinator
from .base import _create_numbers
from .circuit import CIRCUIT_NUMBERS
from .dhw import DHW_NUMBERS
from .pool import POOL_NUMBERS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number entities."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Add circuit 1 numbers if configured
    if coordinator.has_heating_circuit1():
        entities.extend(
            _create_numbers(
                coordinator,
                entry.entry_id,
                CIRCUIT_NUMBERS,
                DEVICE_CIRCUIT_1,
                "circuit1",
                skip_cooling=not coordinator.has_cooling_circuit1(),
            )
        )

    # Add circuit 2 numbers if configured
    if coordinator.has_heating_circuit2():
        entities.extend(
            _create_numbers(
                coordinator,
                entry.entry_id,
                CIRCUIT_NUMBERS,
                DEVICE_CIRCUIT_2,
                "circuit2",
                skip_cooling=not coordinator.has_cooling_circuit2(),
            )
        )

    # Add DHW numbers
    entities.extend(
        _create_numbers(coordinator, entry.entry_id, DHW_NUMBERS, DEVICE_DHW, "dhw")
    )

    # Add pool numbers
    entities.extend(
        _create_numbers(coordinator, entry.entry_id, POOL_NUMBERS, DEVICE_POOL, "pool")
    )

    async_add_entities(entities)
