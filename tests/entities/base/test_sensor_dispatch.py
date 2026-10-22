"""Tests for sensor factory dispatch logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.hitachi_yutaki.entities.base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)
from custom_components.hitachi_yutaki.entities.control_unit.sensors import (
    build_control_unit_sensors,
)


def _make_description(key: str, condition=None) -> HitachiYutakiSensorEntityDescription:
    """Build a minimal sensor description for testing dispatch."""
    return HitachiYutakiSensorEntityDescription(
        key=key,
        condition=condition,
    )


def _make_coordinator() -> MagicMock:
    """Build a mock coordinator for dispatch tests."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {}
    coordinator.hass = MagicMock()
    coordinator.profile.supports_secondary_compressor = False
    return coordinator


class TestSensorDispatch:
    """Tests that _create_sensors creates the correct sensor instances."""

    def test_description_creates_base_sensor(self):
        """A standard description creates HitachiYutakiSensor."""
        coordinator = _make_coordinator()
        descriptions = (_make_description("compressor_frequency"),)

        sensors = _create_sensors(
            coordinator, "test_entry", descriptions, "control_unit"
        )

        assert len(sensors) == 1
        assert type(sensors[0]) is HitachiYutakiSensor

    def test_condition_false_skips_entity(self):
        """Descriptions with a failing condition are not created."""
        coordinator = _make_coordinator()
        descriptions = (_make_description("some_sensor", condition=lambda _: False),)

        sensors = _create_sensors(
            coordinator, "test_entry", descriptions, "control_unit"
        )

        assert len(sensors) == 0

    def test_condition_true_creates_entity(self):
        """Descriptions with a passing condition are created."""
        coordinator = _make_coordinator()
        descriptions = (_make_description("some_sensor", condition=lambda _: True),)

        sensors = _create_sensors(
            coordinator, "test_entry", descriptions, "control_unit"
        )

        assert len(sensors) == 1

    def test_multiple_descriptions_all_create_base_sensor(self):
        """Multiple descriptions all create base HitachiYutakiSensor."""
        coordinator = _make_coordinator()
        descriptions = (
            _make_description("compressor_frequency"),
            _make_description("compressor_cycle_time"),
        )

        sensors = _create_sensors(
            coordinator, "test_entry", descriptions, "control_unit"
        )

        assert len(sensors) == 2
        assert type(sensors[0]) is HitachiYutakiSensor
        assert type(sensors[1]) is HitachiYutakiSensor


@pytest.mark.parametrize(
    ("data", "alarm", "operation"),
    [
        (None, None, None),
        ({}, None, None),
        ({"alarm_code": None, "operation_state_code": None}, None, None),
        ({"alarm_code": 0, "operation_state_code": 0}, None, {"code": 0}),
        ({"alarm_code": 42, "operation_state_code": 6}, {"code": 42}, {"code": 6}),
    ],
)
def test_control_unit_attributes_preserve_codes(data, alarm, operation):
    """Diagnostic descriptions own their attributes, including code zero."""
    coordinator = _make_coordinator()
    coordinator.data = data
    sensors = {
        sensor.entity_description.key: sensor
        for sensor in build_control_unit_sensors(coordinator, "test_entry")
    }
    assert sensors["alarm"].extra_state_attributes == alarm
    assert sensors["operation_state"].extra_state_attributes == operation


@pytest.mark.parametrize("key", ["alarm", "operation_state", "arbitrary_sensor"])
def test_generic_base_does_not_dispatch_on_key(key):
    """Reserved-looking names have no implicit diagnostic behavior."""
    coordinator = _make_coordinator()
    coordinator.data = {"alarm_code": 42, "operation_state_code": 6}
    sensor = _create_sensors(
        coordinator, "test_entry", (_make_description(key),), "control_unit"
    )[0]
    assert sensor.extra_state_attributes is None


@pytest.mark.parametrize("key", ["alarm", "operation_state", "arbitrary_sensor"])
def test_attribute_callback_is_generic_and_works_without_poll_data(key):
    """Computed descriptions can supply attributes before register data exists."""
    coordinator = _make_coordinator()
    coordinator.data = None
    description = _make_description(key)
    description.attributes_fn = MagicMock(return_value={"custom": 7})
    sensor = _create_sensors(coordinator, "test_entry", (description,), "control_unit")[
        0
    ]
    assert sensor.extra_state_attributes == {"custom": 7}
    description.attributes_fn.assert_called_once_with(coordinator)
