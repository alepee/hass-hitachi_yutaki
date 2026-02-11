"""Tests for sensor factory dispatch logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from custom_components.hitachi_yutaki.entities.base.sensor import (
    HitachiYutakiCOPSensor,
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    HitachiYutakiThermalSensor,
    HitachiYutakiTimingSensor,
    _create_sensors,
)


def _make_description(
    key: str, sensor_class=None, condition=None
) -> HitachiYutakiSensorEntityDescription:
    """Build a minimal sensor description for testing dispatch."""
    return HitachiYutakiSensorEntityDescription(
        key=key,
        sensor_class=sensor_class,
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
    """Tests that _create_sensors routes to the correct sensor subclass."""

    def test_cop_description_creates_cop_sensor(self):
        """sensor_class='cop' creates HitachiYutakiCOPSensor."""
        coordinator = _make_coordinator()
        descriptions = (_make_description("cop_heating", sensor_class="cop"),)

        with patch.object(HitachiYutakiCOPSensor, "__init__", return_value=None):
            sensors = _create_sensors(coordinator, "test_entry", descriptions, "control_unit")

        assert len(sensors) == 1
        assert isinstance(sensors[0], HitachiYutakiCOPSensor)

    def test_thermal_description_creates_thermal_sensor(self):
        """sensor_class='thermal' creates HitachiYutakiThermalSensor."""
        coordinator = _make_coordinator()
        descriptions = (_make_description("thermal_power_heating", sensor_class="thermal"),)

        with patch.object(HitachiYutakiThermalSensor, "__init__", return_value=None):
            sensors = _create_sensors(coordinator, "test_entry", descriptions, "control_unit")

        assert len(sensors) == 1
        assert isinstance(sensors[0], HitachiYutakiThermalSensor)

    def test_timing_description_creates_timing_sensor(self):
        """sensor_class='timing' creates HitachiYutakiTimingSensor."""
        coordinator = _make_coordinator()
        descriptions = (_make_description("compressor_cycle_time", sensor_class="timing"),)

        with patch.object(HitachiYutakiTimingSensor, "__init__", return_value=None):
            sensors = _create_sensors(coordinator, "test_entry", descriptions, "control_unit")

        assert len(sensors) == 1
        assert isinstance(sensors[0], HitachiYutakiTimingSensor)

    def test_no_sensor_class_creates_base_sensor(self):
        """No sensor_class (None) creates base HitachiYutakiSensor."""
        coordinator = _make_coordinator()
        descriptions = (_make_description("compressor_frequency"),)

        sensors = _create_sensors(coordinator, "test_entry", descriptions, "control_unit")

        assert len(sensors) == 1
        assert type(sensors[0]) is HitachiYutakiSensor

    def test_condition_false_skips_entity(self):
        """Descriptions with a failing condition are not created."""
        coordinator = _make_coordinator()
        descriptions = (_make_description("some_sensor", condition=lambda _: False),)

        sensors = _create_sensors(coordinator, "test_entry", descriptions, "control_unit")

        assert len(sensors) == 0

    def test_condition_true_creates_entity(self):
        """Descriptions with a passing condition are created."""
        coordinator = _make_coordinator()
        descriptions = (_make_description("some_sensor", condition=lambda _: True),)

        sensors = _create_sensors(coordinator, "test_entry", descriptions, "control_unit")

        assert len(sensors) == 1

    def test_unknown_sensor_class_falls_back_to_base(self):
        """An unrecognized sensor_class falls back to base sensor."""
        coordinator = _make_coordinator()
        descriptions = (_make_description("mystery", sensor_class="unknown"),)

        sensors = _create_sensors(coordinator, "test_entry", descriptions, "control_unit")

        assert len(sensors) == 1
        assert type(sensors[0]) is HitachiYutakiSensor

    def test_mixed_descriptions_dispatch_correctly(self):
        """Multiple descriptions with different sensor_class values dispatch correctly."""
        coordinator = _make_coordinator()
        descriptions = (
            _make_description("compressor_frequency"),
            _make_description("cop_heating", sensor_class="cop"),
            _make_description("thermal_power_heating", sensor_class="thermal"),
            _make_description("compressor_cycle_time", sensor_class="timing"),
        )

        with (
            patch.object(HitachiYutakiCOPSensor, "__init__", return_value=None),
            patch.object(HitachiYutakiThermalSensor, "__init__", return_value=None),
            patch.object(HitachiYutakiTimingSensor, "__init__", return_value=None),
        ):
            sensors = _create_sensors(coordinator, "test_entry", descriptions, "control_unit")

        assert len(sensors) == 4
        assert type(sensors[0]) is HitachiYutakiSensor
        assert isinstance(sensors[1], HitachiYutakiCOPSensor)
        assert isinstance(sensors[2], HitachiYutakiThermalSensor)
        assert isinstance(sensors[3], HitachiYutakiTimingSensor)
