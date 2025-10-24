"""Circuit switches for Hitachi Yutaki integration."""

from typing import Final

from .base import HitachiYutakiSwitchEntityDescription


def _build_circuit_switch_description(
    circuit_id: int,
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


# Legacy constant for backward compatibility
CIRCUIT_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="thermostat",
        name="Thermostat",
        icon="mdi:thermostat",
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
