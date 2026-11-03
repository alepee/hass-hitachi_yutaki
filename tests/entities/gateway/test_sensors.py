"""Tests for gateway sensor value functions."""

from unittest.mock import MagicMock

import pytest

from custom_components.hitachi_yutaki.entities.gateway.sensors import (
    CENTRAL_CONTROL_MODES,
    _build_gateway_sensor_descriptions,
    _central_control_mode_value,
)


def _coordinator(value):
    coordinator = MagicMock()
    coordinator.data = {"central_control_mode": value}
    return coordinator


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0, "local"), (1, "air"), (2, "water"), (3, "full")],
)
def test_central_mode_maps_documented_values(raw, expected):
    """0..3 map to local / air / water / full (PMML0419 "Central Mode")."""
    assert _central_control_mode_value(_coordinator(raw)) == expected


def test_central_mode_unknown_or_missing_is_none():
    """An undocumented value, None, or a missing key yields no state."""
    assert _central_control_mode_value(_coordinator(7)) is None
    assert _central_control_mode_value(_coordinator(None)) is None
    coordinator = MagicMock()
    coordinator.data = {}
    assert _central_control_mode_value(coordinator) is None


def test_central_mode_description_is_gated_on_key_support():
    """The sensor is an ENUM over the documented modes and needs the key."""
    description = next(
        d
        for d in _build_gateway_sensor_descriptions()
        if d.key == "central_control_mode"
    )
    assert description.options == list(CENTRAL_CONTROL_MODES.values())
    coordinator = MagicMock()
    coordinator.api_client.supports_key.return_value = False
    assert description.condition(coordinator) is False
    coordinator.api_client.supports_key.return_value = True
    assert description.condition(coordinator) is True
