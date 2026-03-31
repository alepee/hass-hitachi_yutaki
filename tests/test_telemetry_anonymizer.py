"""Tests for telemetry anonymizer."""

from custom_components.hitachi_yutaki.telemetry.anonymizer import (
    anonymize_point,
    hash_instance_id,
    round_temperature,
)


class TestHashInstanceId:
    """Tests for SHA-256 instance hashing."""

    def test_deterministic(self):
        """Same input always produces same hash."""
        h1 = hash_instance_id("my-instance-id")
        h2 = hash_instance_id("my-instance-id")
        assert h1 == h2

    def test_different_inputs(self):
        """Different inputs produce different hashes."""
        h1 = hash_instance_id("instance-a")
        h2 = hash_instance_id("instance-b")
        assert h1 != h2

    def test_hex_format(self):
        """Hash is a valid hex string of expected length."""
        h = hash_instance_id("test")
        assert len(h) == 64  # SHA-256 = 64 hex chars
        int(h, 16)  # Should not raise

    def test_non_reversible(self):
        """Hash does not contain the original input."""
        h = hash_instance_id("my-secret-id")
        assert "my-secret-id" not in h


class TestRoundTemperature:
    """Tests for temperature rounding."""

    def test_none_passthrough(self):
        """Verify None input returns None without error."""
        assert round_temperature(None) is None

    def test_exact_values(self):
        """Verify values already on the grid are unchanged."""
        assert round_temperature(5.0) == 5.0
        assert round_temperature(5.5) == 5.5
        assert round_temperature(-10.0) == -10.0

    def test_rounding_up(self):
        """Verify values round up to the nearest 0.5 step."""
        assert round_temperature(5.3) == 5.5
        assert round_temperature(5.7) == 5.5

    def test_rounding_down(self):
        """Verify values round down to the nearest 0.5 step."""
        assert round_temperature(5.1) == 5.0
        assert round_temperature(5.9) == 6.0

    def test_negative_temperatures(self):
        """Verify rounding works correctly for negative values."""
        assert round_temperature(-2.3) == -2.5
        assert round_temperature(-2.1) == -2.0

    def test_custom_precision(self):
        """Verify rounding respects a custom precision step."""
        assert round_temperature(5.3, precision=1.0) == 5.0
        assert round_temperature(5.7, precision=1.0) == 6.0


class TestAnonymizePoint:
    """Tests for dict-based point anonymization."""

    def test_temperature_keys_rounded(self):
        """All keys containing '_temp' are rounded to 0.5 degrees C."""
        point = {
            "outdoor_temp": 5.3,
            "water_inlet_temp": 34.8,
            "dhw_current_temp": 51.7,
            "compressor_frequency": 65.0,
        }
        result = anonymize_point(point)
        assert result["outdoor_temp"] == 5.5
        assert result["water_inlet_temp"] == 35.0
        assert result["dhw_current_temp"] == 51.5
        assert result["compressor_frequency"] == 65.0

    def test_cop_keys_rounded_to_one_decimal(self):
        """COP values are rounded to 1 decimal place."""
        point = {"cop_heating": 1.3456, "cop_cooling": 2.789}
        result = anonymize_point(point)
        assert result["cop_heating"] == 1.3
        assert result["cop_cooling"] == 2.8

    def test_cop_metadata_not_rounded(self):
        """COP quality, measurements, time_span are not rounded."""
        point = {
            "cop_heating_quality": "optimal",
            "cop_heating_measurements": 42,
            "cop_heating_time_span_minutes": 15.3,
        }
        result = anonymize_point(point)
        assert result["cop_heating_quality"] == "optimal"
        assert result["cop_heating_measurements"] == 42
        assert result["cop_heating_time_span_minutes"] == 15.3

    def test_water_flow_rounded(self):
        """Water flow is rounded to 1 decimal."""
        point = {"water_flow": 12.345}
        result = anonymize_point(point)
        assert result["water_flow"] == 12.3

    def test_power_rounded_to_two_decimals(self):
        """Thermal and electrical power rounded to 2 decimals."""
        point = {"thermal_power_heating": 5.2345, "electrical_power": 1.8678}
        result = anonymize_point(point)
        assert result["thermal_power_heating"] == 5.23
        assert result["electrical_power"] == 1.87

    def test_none_values_preserved(self):
        """None values pass through unchanged."""
        point = {"outdoor_temp": None, "cop_heating": None}
        result = anonymize_point(point)
        assert result["outdoor_temp"] is None
        assert result["cop_heating"] is None

    def test_non_numeric_values_unchanged(self):
        """String and boolean values pass through."""
        point = {
            "operation_state": "heat_on",
            "unit_power": True,
            "time": "2026-03-31T12:00:00Z",
        }
        result = anonymize_point(point)
        assert result["operation_state"] == "heat_on"
        assert result["unit_power"] is True

    def test_does_not_mutate_original(self):
        """anonymize_point returns a new dict."""
        point = {"outdoor_temp": 5.3}
        result = anonymize_point(point)
        assert result is not point
        assert point["outdoor_temp"] == 5.3
