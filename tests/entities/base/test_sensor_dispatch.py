"""Tests for sensor factory dispatch logic."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.hitachi_yutaki.entities.base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
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
