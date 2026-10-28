"""Circuit switch descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.hitachi_yutaki.const import CIRCUIT_IDS, DEVICE_TYPES
from homeassistant.const import EntityCategory

from ..base.switch import (
    HitachiYutakiSwitch,
    HitachiYutakiSwitchEntityDescription,
    _create_switches,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_circuit_switches(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    circuit_id: CIRCUIT_IDS,
    device_type: DEVICE_TYPES,
) -> list[HitachiYutakiSwitch]:
    """Build circuit switch entities."""

    descriptions = _build_circuit_switch_descriptions(circuit_id)
    return _create_switches(
        coordinator, entry_id, descriptions, device_type, f"circuit{circuit_id}"
    )


def _build_circuit_switch_descriptions(
    circuit_id: CIRCUIT_IDS,
) -> tuple[HitachiYutakiSwitchEntityDescription, ...]:
    """Build circuit switch descriptions for a specific circuit ID."""
    return (
        # Writes the gateway's "Thermostat Available" flag. ON tells the heat
        # pump to regulate on the room temperature Home Assistant writes
        # (the Room temperature number or the set_room_temperature action),
        # seeded with the setpoint first (see the API method); OFF leaves it
        # to its water law or to a thermostat wired to the unit.
        # Field test (#137): the flag is inert while system_config reports a
        # bound Hitachi thermostat, so it is not gated on those bits; the unit
        # already regulates on the Modbus room value in that case.
        HitachiYutakiSwitchEntityDescription(
            key="external_room_sensor",
            translation_key="external_room_sensor",
            icon="mdi:home-thermometer",
            entity_category=EntityCategory.CONFIG,
            condition=lambda c: c.api_client.can_write(
                f"circuit{circuit_id}_thermostat"
            ),
            get_fn=lambda api, circuit_id: api.get_circuit_thermostat(circuit_id),
            set_fn=lambda api, circuit_id, enabled: api.set_external_room_sensor(
                circuit_id, enabled
            ),
        ),
        HitachiYutakiSwitchEntityDescription(
            key="eco_mode",
            name="Eco Mode",
            icon="mdi:leaf",
            condition=lambda c: c.api_client.can_write(f"circuit{circuit_id}_eco_mode"),
            get_fn=lambda api, circuit_id: api.get_circuit_eco_mode(circuit_id),
            set_fn=lambda api, circuit_id, enabled: api.set_circuit_eco_mode(
                circuit_id, enabled
            ),
        ),
    )
