"""Circuit switch descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.hitachi_yutaki.const import CIRCUIT_IDS, DEVICE_TYPES

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
        HitachiYutakiSwitchEntityDescription(
            key="thermostat",
            name="Thermostat",
            icon="mdi:thermostat",
            condition=lambda c: c.data.get(
                f"circuit{circuit_id}_thermostat_available", False
            ),
            get_fn=lambda api, circuit_id: api.get_circuit_thermostat(circuit_id),
            set_fn=lambda api, circuit_id, enabled: api.set_circuit_thermostat(
                circuit_id, enabled
            ),
        ),
        HitachiYutakiSwitchEntityDescription(
            key="eco_mode",
            name="Eco Mode",
            icon="mdi:leaf",
            get_fn=lambda api, circuit_id: api.get_circuit_eco_mode(circuit_id),
            set_fn=lambda api, circuit_id, enabled: api.set_circuit_eco_mode(
                circuit_id, enabled
            ),
        ),
    )
