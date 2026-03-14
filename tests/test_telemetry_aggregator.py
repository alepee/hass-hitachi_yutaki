"""Tests for telemetry aggregator."""

from datetime import UTC, date, datetime

from custom_components.hitachi_yutaki.telemetry.aggregator import aggregate_metrics
from custom_components.hitachi_yutaki.telemetry.models import MetricPoint

HASH = "abc123"
DATE = date(2025, 3, 6)


def _point(seconds_offset: int = 0, **kwargs) -> MetricPoint:
    """Create a MetricPoint with a time offset in seconds."""
    return MetricPoint(
        time=datetime(2025, 3, 6, 0, 0, seconds_offset, tzinfo=UTC),
        **kwargs,
    )


class TestAggregateEmpty:
    """Tests for empty input."""

    def test_empty_list(self):
        """Verify aggregation of an empty list returns zeroed defaults."""
        stats = aggregate_metrics(HASH, DATE, [])
        assert stats.instance_hash == HASH
        assert stats.date == DATE
        assert stats.outdoor_temp_min is None
        assert stats.cop_avg is None
        assert stats.compressor_starts == 0
        assert stats.thermal_energy_kwh == 0.0


class TestAggregateTemperatures:
    """Tests for temperature aggregation."""

    def test_single_point(self):
        """Verify min, max, and avg are equal for a single data point."""
        points = [_point(outdoor_temp=5.0)]
        stats = aggregate_metrics(HASH, DATE, points)
        assert stats.outdoor_temp_min == 5.0
        assert stats.outdoor_temp_max == 5.0
        assert stats.outdoor_temp_avg == 5.0

    def test_multiple_points(self):
        """Verify min, max, and avg are computed correctly across multiple points."""
        points = [
            _point(0, outdoor_temp=-2.0),
            _point(5, outdoor_temp=5.0),
            _point(10, outdoor_temp=12.0),
        ]
        stats = aggregate_metrics(HASH, DATE, points)
        assert stats.outdoor_temp_min == -2.0
        assert stats.outdoor_temp_max == 12.0
        assert stats.outdoor_temp_avg == 5.0

    def test_all_none_temps(self):
        """Verify temperature stats remain None when no temperature data exists."""
        points = [_point(0), _point(5)]
        stats = aggregate_metrics(HASH, DATE, points)
        assert stats.outdoor_temp_min is None
        assert stats.outdoor_temp_avg is None


class TestAggregateCOP:
    """Tests for COP aggregation."""

    def test_cop_stats(self):
        """Verify COP min, max, avg, and best quality are computed correctly."""
        points = [
            _point(0, cop_instant=2.5, cop_quality="preliminary"),
            _point(5, cop_instant=3.5, cop_quality="optimal"),
            _point(10, cop_instant=4.0, cop_quality="optimal"),
        ]
        stats = aggregate_metrics(HASH, DATE, points)
        assert stats.cop_min == 2.5
        assert stats.cop_max == 4.0
        assert abs(stats.cop_avg - 10.0 / 3) < 0.001
        assert stats.cop_quality_best == "optimal"

    def test_cop_quality_picks_best(self):
        """Verify the highest quality level is selected among all points."""
        points = [
            _point(0, cop_quality="no_data"),
            _point(5, cop_quality="preliminary"),
            _point(10, cop_quality="insufficient_data"),
        ]
        stats = aggregate_metrics(HASH, DATE, points)
        assert stats.cop_quality_best == "preliminary"


class TestAggregateCompressor:
    """Tests for compressor start counting."""

    def test_no_transitions(self):
        """Verify no starts counted when compressor stays continuously on."""
        points = [
            _point(0, compressor_on=True),
            _point(5, compressor_on=True),
        ]
        stats = aggregate_metrics(HASH, DATE, points)
        assert stats.compressor_starts == 0

    def test_one_start(self):
        """Verify a single off-to-on transition counts as one start."""
        points = [
            _point(0, compressor_on=False),
            _point(5, compressor_on=True),
            _point(10, compressor_on=True),
        ]
        stats = aggregate_metrics(HASH, DATE, points)
        assert stats.compressor_starts == 1

    def test_multiple_starts(self):
        """Verify multiple off-to-on transitions are counted correctly."""
        points = [
            _point(0, compressor_on=False),
            _point(5, compressor_on=True),
            _point(10, compressor_on=False),
            _point(15, compressor_on=True),
            _point(20, compressor_on=False),
            _point(25, compressor_on=True),
        ]
        stats = aggregate_metrics(HASH, DATE, points)
        assert stats.compressor_starts == 3

    def test_compressor_hours(self):
        """3 samples at 5s interval = 15s of compressor time."""
        points = [
            _point(0, compressor_on=True),
            _point(5, compressor_on=True),
            _point(10, compressor_on=True),
        ]
        stats = aggregate_metrics(HASH, DATE, points)
        expected_hours = 3 * (5.0 / 3600.0)
        assert abs(stats.compressor_hours - expected_hours) < 1e-9


class TestAggregateDefrost:
    """Tests for defrost counting."""

    def test_defrost_transitions(self):
        """Verify defrost cycles are counted from off-to-on transitions."""
        points = [
            _point(0, is_defrosting=False),
            _point(5, is_defrosting=True),
            _point(10, is_defrosting=True),
            _point(15, is_defrosting=False),
            _point(20, is_defrosting=True),
            _point(25, is_defrosting=False),
        ]
        stats = aggregate_metrics(HASH, DATE, points)
        assert stats.defrost_count == 2

    def test_defrost_minutes(self):
        """3 defrost samples × 5s = 15s ≈ 0.25 minutes."""
        points = [
            _point(0, is_defrosting=True),
            _point(5, is_defrosting=True),
            _point(10, is_defrosting=True),
        ]
        stats = aggregate_metrics(HASH, DATE, points)
        expected_minutes = 3 * (5.0 / 3600.0) * 60.0
        assert abs(stats.defrost_total_minutes - expected_minutes) < 1e-9


class TestAggregateModeHours:
    """Tests for mode hour tracking."""

    def test_heating_hours(self):
        """Verify heating and cooling hours are accumulated from mode samples."""
        points = [
            _point(0, unit_mode="heat"),
            _point(5, unit_mode="heat"),
            _point(10, unit_mode="cool"),
        ]
        stats = aggregate_metrics(HASH, DATE, points)
        expected_heat = 2 * (5.0 / 3600.0)
        expected_cool = 1 * (5.0 / 3600.0)
        assert abs(stats.heating_hours - expected_heat) < 1e-9
        assert abs(stats.cooling_hours - expected_cool) < 1e-9

    def test_dhw_hours(self):
        """Verify DHW active hours are accumulated from boolean samples."""
        points = [
            _point(0, dhw_active=True),
            _point(5, dhw_active=True),
            _point(10, dhw_active=False),
        ]
        stats = aggregate_metrics(HASH, DATE, points)
        expected_dhw = 2 * (5.0 / 3600.0)
        assert abs(stats.dhw_hours - expected_dhw) < 1e-9


class TestAggregateEnergy:
    """Tests for energy aggregation."""

    def test_energy_from_power(self):
        """Power (kW) × time (hours) = energy (kWh)."""
        points = [
            _point(0, thermal_power=10.0, electrical_power=3.0),
            _point(5, thermal_power=12.0, electrical_power=4.0),
        ]
        stats = aggregate_metrics(HASH, DATE, points)
        interval_h = 5.0 / 3600.0
        assert abs(stats.thermal_energy_kwh - 22.0 * interval_h) < 1e-9
        assert abs(stats.electrical_energy_kwh - 7.0 * interval_h) < 1e-9

    def test_no_power_data(self):
        """Verify energy stays at zero when no power data is present."""
        points = [_point(0), _point(5)]
        stats = aggregate_metrics(HASH, DATE, points)
        assert stats.thermal_energy_kwh == 0.0
        assert stats.electrical_energy_kwh == 0.0
