"""Switch platform for Hitachi Yutaki integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import (
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_CONTROL_UNIT,
    DEVICE_DHW,
    DEVICE_POOL,
    DOMAIN,
)
from ..coordinator import HitachiYutakiDataCoordinator
from .base import _create_switches
from .circuit import _build_circuit_switch_description
from .control_unit import _build_control_unit_switch_description
from .dhw import _build_dhw_switch_description
from .pool import _build_pool_switch_description


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    # Add unit switches
    control_unit_descriptions = _build_control_unit_switch_description()
    entities.extend(
        _create_switches(
            coordinator,
            config_entry.entry_id,
            control_unit_descriptions,
            DEVICE_CONTROL_UNIT,
        )
    )

    # Add circuit 1 switches if configured
    if coordinator.has_circuit1_heating() or coordinator.has_circuit1_cooling():
        circuit1_descriptions = _build_circuit_switch_description(1)
        entities.extend(
            _create_switches(
                coordinator,
                config_entry.entry_id,
                circuit1_descriptions,
                DEVICE_CIRCUIT_1,
                "circuit1",
            )
        )

    # Add circuit 2 switches if configured
    if coordinator.has_circuit2_heating() or coordinator.has_circuit2_cooling():
        circuit2_descriptions = _build_circuit_switch_description(2)
        entities.extend(
            _create_switches(
                coordinator,
                config_entry.entry_id,
                circuit2_descriptions,
                DEVICE_CIRCUIT_2,
                "circuit2",
            )
        )

    # Add DHW switches
    dhw_descriptions = _build_dhw_switch_description()
    entities.extend(
        _create_switches(
            coordinator, config_entry.entry_id, dhw_descriptions, DEVICE_DHW, "dhw"
        )
    )

    # Add pool switches
    pool_descriptions = _build_pool_switch_description()
    entities.extend(
        _create_switches(
            coordinator, config_entry.entry_id, pool_descriptions, DEVICE_POOL, "pool"
        )
    )

    async_add_entities(entities)
