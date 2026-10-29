"""Tests for circuit sensor descriptions."""

from unittest.mock import MagicMock

from custom_components.hitachi_yutaki.const import (
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
)
from custom_components.hitachi_yutaki.entities.circuit.sensors import (
    _build_circuit_sensor_descriptions,
)


def _coordinator(value, supported=True):
    coordinator = MagicMock()
    coordinator.data = {"circuit2_mixing_valve_position": value}
    coordinator.api_client.supports_key.return_value = supported
    return coordinator


def test_circuit_1_has_no_sensors():
    """The mixing valve belongs to circuit 2 only."""
    assert _build_circuit_sensor_descriptions(CIRCUIT_PRIMARY_ID) == ()


def test_circuit_2_mixing_valve_position():
    """Circuit 2 gets the mixing valve sensor, reading the polled percentage."""
    (description,) = _build_circuit_sensor_descriptions(CIRCUIT_SECONDARY_ID)
    assert description.key == "circuit2_mixing_valve_position"
    assert description.value_fn(_coordinator(42)) == 42


def test_mixing_valve_gated_on_the_map_and_disabled_by_default():
    """Created wherever the map has the key, opt-in: 0 is not a presence signal."""
    (description,) = _build_circuit_sensor_descriptions(CIRCUIT_SECONDARY_ID)
    assert description.condition(_coordinator(42)) is True
    assert description.condition(_coordinator(0)) is True
    assert description.condition(_coordinator(None)) is True
    assert description.condition(_coordinator(42, supported=False)) is False
    assert description.entity_registry_enabled_default is False
