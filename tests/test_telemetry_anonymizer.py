"""Tests for telemetry anonymizer."""

from datetime import UTC, date, datetime

from custom_components.hitachi_yutaki.telemetry.anonymizer import (
    anonymize_daily_stats,
    anonymize_metric_point,
    hash_instance_id,
    round_temperature,
)
from custom_components.hitachi_yutaki.telemetry.models import DailyStats, MetricPoint


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


class TestAnonymizeMetricPoint:
    """Tests for MetricPoint anonymization."""

    def test_temperatures_rounded(self):
        """Verify all temperature fields are rounded to 0.5 steps."""
        point = MetricPoint(
            time=datetime(2025, 3, 6, 20, 0, 0, tzinfo=UTC),
            outdoor_temp=5.37,
            water_inlet_temp=34.82,
            water_outlet_temp=40.14,
            dhw_temp=52.67,
            circuit1_water_temp=38.33,
            circuit2_water_temp=29.91,
        )
        anon = anonymize_metric_point(point)
        assert anon.outdoor_temp == 5.5
        assert anon.water_inlet_temp == 35.0
        assert anon.water_outlet_temp == 40.0
        assert anon.dhw_temp == 52.5
        assert anon.circuit1_water_temp == 38.5
        assert anon.circuit2_water_temp == 30.0

    def test_cop_rounded_to_one_decimal(self):
        """Verify COP is rounded to one decimal place."""
        point = MetricPoint(
            time=datetime(2025, 3, 6, 20, 0, 0, tzinfo=UTC),
            cop_instant=3.456,
        )
        anon = anonymize_metric_point(point)
        assert anon.cop_instant == 3.5

    def test_none_values_preserved(self):
        """Verify None fields remain None after anonymization."""
        point = MetricPoint(
            time=datetime(2025, 3, 6, 20, 0, 0, tzinfo=UTC),
        )
        anon = anonymize_metric_point(point)
        assert anon.outdoor_temp is None
        assert anon.cop_instant is None

    def test_non_temperature_fields_unchanged(self):
        """Verify non-temperature fields pass through without modification."""
        point = MetricPoint(
            time=datetime(2025, 3, 6, 20, 0, 0, tzinfo=UTC),
            compressor_on=True,
            compressor_frequency=65.3,
            compressor_current=8.7,
            thermal_power=12.345,
            electrical_power=3.456,
            unit_mode="heat",
            is_defrosting=False,
            dhw_active=True,
        )
        anon = anonymize_metric_point(point)
        assert anon.compressor_on is True
        assert anon.compressor_frequency == 65.3
        assert anon.compressor_current == 8.7
        assert anon.thermal_power == 12.345
        assert anon.electrical_power == 3.456
        assert anon.unit_mode == "heat"
        assert anon.is_defrosting is False
        assert anon.dhw_active is True

    def test_timestamp_preserved(self):
        """Verify the original timestamp is preserved after anonymization."""
        ts = datetime(2025, 3, 6, 20, 0, 0, tzinfo=UTC)
        point = MetricPoint(time=ts, outdoor_temp=5.37)
        anon = anonymize_metric_point(point)
        assert anon.time == ts


class TestAnonymizeDailyStats:
    """Tests for DailyStats anonymization."""

    def test_temperatures_rounded(self):
        """Verify daily temperature stats are rounded to 0.5 steps."""
        stats = DailyStats(
            instance_hash="abc",
            date=date(2025, 3, 6),
            outdoor_temp_min=-2.37,
            outdoor_temp_max=12.82,
            outdoor_temp_avg=5.14,
        )
        anon = anonymize_daily_stats(stats)
        assert anon.outdoor_temp_min == -2.5
        assert anon.outdoor_temp_max == 13.0
        assert anon.outdoor_temp_avg == 5.0

    def test_cop_rounded(self):
        """Verify daily COP stats are rounded to one decimal place."""
        stats = DailyStats(
            instance_hash="abc",
            date=date(2025, 3, 6),
            cop_avg=3.456,
            cop_min=2.134,
            cop_max=4.789,
        )
        anon = anonymize_daily_stats(stats)
        assert anon.cop_avg == 3.5
        assert anon.cop_min == 2.1
        assert anon.cop_max == 4.8

    def test_energy_rounded(self):
        """Verify energy values are rounded to one decimal place."""
        stats = DailyStats(
            instance_hash="abc",
            date=date(2025, 3, 6),
            thermal_energy_kwh=42.3456,
            electrical_energy_kwh=12.7891,
        )
        anon = anonymize_daily_stats(stats)
        assert anon.thermal_energy_kwh == 42.3
        assert anon.electrical_energy_kwh == 12.8

    def test_hours_rounded(self):
        """Verify hour and minute durations are rounded to one decimal place."""
        stats = DailyStats(
            instance_hash="abc",
            date=date(2025, 3, 6),
            compressor_hours=18.456,
            heating_hours=12.345,
            cooling_hours=0.0,
            dhw_hours=6.111,
            defrost_total_minutes=23.456,
        )
        anon = anonymize_daily_stats(stats)
        assert anon.compressor_hours == 18.5
        assert anon.heating_hours == 12.3
        assert anon.cooling_hours == 0.0
        assert anon.dhw_hours == 6.1
        assert anon.defrost_total_minutes == 23.5

    def test_integer_fields_unchanged(self):
        """Verify integer count fields are not modified by anonymization."""
        stats = DailyStats(
            instance_hash="abc",
            date=date(2025, 3, 6),
            compressor_starts=15,
            defrost_count=3,
        )
        anon = anonymize_daily_stats(stats)
        assert anon.compressor_starts == 15
        assert anon.defrost_count == 3

    def test_none_values_preserved(self):
        """Verify None fields remain None after anonymization."""
        stats = DailyStats(
            instance_hash="abc",
            date=date(2025, 3, 6),
        )
        anon = anonymize_daily_stats(stats)
        assert anon.outdoor_temp_min is None
        assert anon.cop_avg is None
