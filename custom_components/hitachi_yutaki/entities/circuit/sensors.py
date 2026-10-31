"""Circuit sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.hitachi_yutaki.const import (
    CIRCUIT_IDS,
    CIRCUIT_SECONDARY_ID,
    DEVICE_TYPES,
)
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity import EntityCategory

from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_circuit_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    circuit_id: CIRCUIT_IDS,
    device_type: DEVICE_TYPES,
) -> list[HitachiYutakiSensor]:
    """Build circuit sensor entities."""
    descriptions = _build_circuit_sensor_descriptions(circuit_id)
    return _create_sensors(coordinator, entry_id, descriptions, device_type)


def _build_circuit_sensor_descriptions(
    circuit_id: CIRCUIT_IDS,
) -> tuple[HitachiYutakiSensorEntityDescription, ...]:
    """Build circuit sensor descriptions (only circuit 2 has a mixing valve)."""
    if circuit_id != CIRCUIT_SECONDARY_ID:
        return ()
    return (
        HitachiYutakiSensorEntityDescription(
            key="circuit2_mixing_valve_position",
            translation_key="mixing_valve_position",
            description="Opening of the circuit 2 mixing valve",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:valve",
            # The gateway reports 0, not a sentinel, without a mixing kit, so
            # presence cannot be detected: opt-in instead of a fake 0 %.
            condition=lambda c: c.api_client.supports_key(
                "circuit2_mixing_valve_position"
            ),
            entity_registry_enabled_default=False,
            value_fn=lambda c: c.data.get("circuit2_mixing_valve_position"),
        ),
    )
