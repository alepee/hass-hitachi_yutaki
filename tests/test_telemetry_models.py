"""Tests for telemetry data models."""

from datetime import UTC, date, datetime

from custom_components.hitachi_yutaki.telemetry.models import (
    DailyStats,
    InstallationInfo,
    MetricPoint,
    MetricsBatch,
    RegisterSnapshot,
    TelemetryLevel,
)


class TestTelemetryLevel:
    """Tests for TelemetryLevel enum."""

    def test_values(self):
        """Verify enum members have expected string values."""
        assert TelemetryLevel.OFF.value == "off"
        assert TelemetryLevel.BASIC.value == "basic"
        assert TelemetryLevel.FULL.value == "full"

    def test_from_string(self):
        """Verify enum can be constructed from string values."""
        assert TelemetryLevel("off") == TelemetryLevel.OFF
        assert TelemetryLevel("basic") == TelemetryLevel.BASIC
        assert TelemetryLevel("full") == TelemetryLevel.FULL


class TestInstallationInfo:
    """Tests for InstallationInfo dataclass."""

    def _make_info(self, **overrides):
        """Create an InstallationInfo with sensible defaults and optional overrides."""
        defaults = {
            "instance_hash": "abc123",
            "profile": "yutaki_s80",
            "gateway_type": "modbus_atw_mbs_02",
            "ha_version": "2025.3.1",
            "integration_version": "2.0.1",
            "power_supply": "single",
            "has_dhw": True,
            "has_pool": False,
            "has_cooling": True,
            "max_circuits": 2,
            "has_secondary_compressor": True,
        }
        defaults.update(overrides)
        return InstallationInfo(**defaults)

    def test_creation(self):
        """Verify fields are assigned correctly on construction."""
        info = self._make_info()
        assert info.profile == "yutaki_s80"
        assert info.has_dhw is True
        assert info.max_circuits == 2

    def test_frozen(self):
        """Verify the dataclass is immutable (frozen)."""
        info = self._make_info()
        try:
            info.profile = "other"  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass

    def test_to_dict(self):
        """Verify to_dict produces the expected structure with type and data keys."""
        info = self._make_info()
        d = info.to_dict()
        assert d["type"] == "installation"
        assert d["instance_hash"] == "abc123"
        assert d["data"]["profile"] == "yutaki_s80"
        assert d["data"]["has_secondary_compressor"] is True
        # instance_hash should NOT appear in data (it's at the top level)
        assert "instance_hash" not in d["data"]


class TestMetricPoint:
    """Tests for MetricPoint dataclass."""

    def _make_point(self, **overrides):
        """Create a MetricPoint with a fixed timestamp and optional overrides."""
        defaults = {"time": datetime(2025, 3, 6, 20, 0, 0, tzinfo=UTC)}
        defaults.update(overrides)
        return MetricPoint(**defaults)

    def test_creation_minimal(self):
        """Verify optional fields default to None when not provided."""
        point = self._make_point()
        assert point.outdoor_temp is None
        assert point.compressor_on is None

    def test_creation_full(self):
        """Verify all fields are correctly assigned when fully populated."""
        point = self._make_point(
            outdoor_temp=5.5,
            water_inlet_temp=35.0,
            water_outlet_temp=40.5,
            compressor_on=True,
            cop_instant=3.2,
            unit_mode="heat",
            is_defrosting=False,
        )
        assert point.outdoor_temp == 5.5
        assert point.compressor_on is True
        assert point.unit_mode == "heat"

    def test_to_dict_omits_none(self):
        """Verify to_dict excludes fields with None values."""
        point = self._make_point(outdoor_temp=5.5, compressor_on=True)
        d = point.to_dict()
        assert "time" in d
        assert d["outdoor_temp"] == 5.5
        assert d["compressor_on"] is True
        # None fields should be absent
        assert "water_inlet_temp" not in d
        assert "cop_instant" not in d

    def test_to_dict_time_format(self):
        """Verify timestamp is serialized as ISO 8601 string."""
        point = self._make_point()
        d = point.to_dict()
        assert d["time"] == "2025-03-06T20:00:00+00:00"


class TestMetricsBatch:
    """Tests for MetricsBatch dataclass."""

    def test_empty_batch(self):
        """Verify an empty batch serializes with an empty points list."""
        batch = MetricsBatch(instance_hash="abc123")
        assert batch.points == []
        d = batch.to_dict()
        assert d["type"] == "metrics"
        assert d["instance_hash"] == "abc123"
        assert d["points"] == []

    def test_batch_with_points(self):
        """Verify batch serializes all contained metric points."""
        points = [
            MetricPoint(
                time=datetime(2025, 3, 6, 20, 0, 0, tzinfo=UTC),
                outdoor_temp=5.5,
            ),
            MetricPoint(
                time=datetime(2025, 3, 6, 20, 0, 5, tzinfo=UTC),
                outdoor_temp=5.0,
            ),
        ]
        batch = MetricsBatch(instance_hash="abc123", points=points)
        d = batch.to_dict()
        assert len(d["points"]) == 2
        assert d["points"][0]["outdoor_temp"] == 5.5
        assert d["points"][1]["outdoor_temp"] == 5.0


class TestDailyStats:
    """Tests for DailyStats dataclass."""

    def _make_stats(self, **overrides):
        """Create a DailyStats with sensible defaults and optional overrides."""
        defaults = {
            "instance_hash": "abc123",
            "date": date(2025, 3, 6),
        }
        defaults.update(overrides)
        return DailyStats(**defaults)

    def test_creation_defaults(self):
        """Verify numeric fields default to zero and optional fields to None."""
        stats = self._make_stats()
        assert stats.compressor_starts == 0
        assert stats.compressor_hours == 0.0
        assert stats.outdoor_temp_min is None

    def test_creation_with_data(self):
        """Verify all fields are correctly assigned when populated."""
        stats = self._make_stats(
            outdoor_temp_min=-2.0,
            outdoor_temp_max=12.5,
            outdoor_temp_avg=5.5,
            cop_avg=3.5,
            compressor_starts=15,
            thermal_energy_kwh=42.3,
        )
        assert stats.outdoor_temp_min == -2.0
        assert stats.cop_avg == 3.5
        assert stats.compressor_starts == 15

    def test_to_dict(self):
        """Verify to_dict produces the expected structure with date and data keys."""
        stats = self._make_stats(
            outdoor_temp_min=-2.0,
            outdoor_temp_max=12.5,
            cop_avg=3.5,
        )
        d = stats.to_dict()
        assert d["type"] == "daily_stats"
        assert d["instance_hash"] == "abc123"
        assert d["date"] == "2025-03-06"
        assert d["data"]["outdoor_temp_min"] == -2.0
        assert d["data"]["cop_avg"] == 3.5

    def test_to_dict_includes_zero_values(self):
        """Zero is a valid value and should be included."""
        stats = self._make_stats(compressor_starts=0, heating_hours=0.0)
        d = stats.to_dict()
        assert d["data"]["compressor_starts"] == 0
        assert d["data"]["heating_hours"] == 0.0


class TestRegisterSnapshot:
    """Tests for RegisterSnapshot dataclass."""

    def test_creation_and_serialization(self):
        """Verify snapshot serializes with type, profile, and register data."""
        snapshot = RegisterSnapshot(
            instance_hash="abc123",
            time=datetime(2025, 3, 6, 20, 0, 0, tzinfo=UTC),
            profile="yutaki_s80",
            gateway_type="modbus_atw_mbs_02",
            registers={"outdoor_temp": 55, "water_inlet_temp": 350, "unit_mode": 1},
        )
        d = snapshot.to_dict()
        assert d["type"] == "snapshot"
        assert d["instance_hash"] == "abc123"
        assert d["profile"] == "yutaki_s80"
        assert d["registers"]["outdoor_temp"] == 55
        assert d["time"] == "2025-03-06T20:00:00+00:00"
