"""Tests for hydraulic sensor descriptions and conditional visibility."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.hitachi_yutaki.entities.hydraulic.sensors import (
    _build_hydraulic_sensor_descriptions,
    build_hydraulic_sensors,
)


def _make_coordinator(data: dict | None = None) -> MagicMock:
    """Build a mock coordinator with optional data overrides."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {}
    coordinator.hass = MagicMock()
    coordinator.data = data or {}
    return coordinator


class TestHydraulicSensorDescriptions:
    """Tests for _build_hydraulic_sensor_descriptions."""

    def test_descriptions_include_two2_and_two3(self):
        """Two2 and Two3 descriptions exist in the builder output."""
        descriptions = _build_hydraulic_sensor_descriptions()
        keys = [d.key for d in descriptions]
        assert "water_outlet_2_temp" in keys
        assert "water_outlet_3_temp" in keys

    def test_two2_and_two3_have_conditions(self):
        """Two2 and Two3 descriptions have non-None condition callbacks."""
        descriptions = _build_hydraulic_sensor_descriptions()
        two2 = next(d for d in descriptions if d.key == "water_outlet_2_temp")
        two3 = next(d for d in descriptions if d.key == "water_outlet_3_temp")
        assert two2.condition is not None
        assert two3.condition is not None

    def test_base_sensors_have_no_condition(self):
        """Base hydraulic sensors (inlet, outlet, target) have no condition."""
        descriptions = _build_hydraulic_sensor_descriptions()
        base_keys = {"water_inlet_temp", "water_outlet_temp", "water_target_temp"}
        for desc in descriptions:
            if desc.key in base_keys:
                assert desc.condition is None, f"{desc.key} should have no condition"


class TestHydraulicSensorConditionalVisibility:
    """Tests for Two2/Two3 conditional creation."""

    def test_two2_created_when_sensor_connected(self):
        """Two2 entity created when register returns valid temperature."""
        coordinator = _make_coordinator({"water_outlet_2_temp": 35})
        sensors = build_hydraulic_sensors(coordinator, "test_entry")
        keys = [s.entity_description.key for s in sensors]
        assert "water_outlet_2_temp" in keys

    def test_two2_not_created_when_sensor_disconnected(self):
        """Two2 entity not created when gateway returns None (sentinel filtered)."""
        coordinator = _make_coordinator({"water_outlet_2_temp": None})
        sensors = build_hydraulic_sensors(coordinator, "test_entry")
        keys = [s.entity_description.key for s in sensors]
        assert "water_outlet_2_temp" not in keys

    def test_two2_not_created_when_value_none(self):
        """Two2 entity not created when register returns None."""
        coordinator = _make_coordinator({"water_outlet_2_temp": None})
        sensors = build_hydraulic_sensors(coordinator, "test_entry")
        keys = [s.entity_description.key for s in sensors]
        assert "water_outlet_2_temp" not in keys

    def test_two2_not_created_when_key_missing(self):
        """Two2 entity not created when data key is absent."""
        coordinator = _make_coordinator({})
        sensors = build_hydraulic_sensors(coordinator, "test_entry")
        keys = [s.entity_description.key for s in sensors]
        assert "water_outlet_2_temp" not in keys

    def test_two3_created_when_sensor_connected(self):
        """Two3 entity created when register returns valid temperature."""
        coordinator = _make_coordinator({"water_outlet_3_temp": 42})
        sensors = build_hydraulic_sensors(coordinator, "test_entry")
        keys = [s.entity_description.key for s in sensors]
        assert "water_outlet_3_temp" in keys

    def test_two3_not_created_when_sensor_disconnected(self):
        """Two3 entity not created when gateway returns None (sentinel filtered)."""
        coordinator = _make_coordinator({"water_outlet_3_temp": None})
        sensors = build_hydraulic_sensors(coordinator, "test_entry")
        keys = [s.entity_description.key for s in sensors]
        assert "water_outlet_3_temp" not in keys

    def test_two2_created_with_zero_value(self):
        """Two2 entity created when temperature is 0°C (valid reading)."""
        coordinator = _make_coordinator({"water_outlet_2_temp": 0})
        sensors = build_hydraulic_sensors(coordinator, "test_entry")
        keys = [s.entity_description.key for s in sensors]
        assert "water_outlet_2_temp" in keys

    def test_two2_created_with_negative_value(self):
        """Two2 entity created for negative temps that aren't -127."""
        coordinator = _make_coordinator({"water_outlet_2_temp": -10})
        sensors = build_hydraulic_sensors(coordinator, "test_entry")
        keys = [s.entity_description.key for s in sensors]
        assert "water_outlet_2_temp" in keys
