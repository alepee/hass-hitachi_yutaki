"""Tests for telemetry data models."""

from datetime import UTC, datetime

from custom_components.hitachi_yutaki.telemetry.models import (
    InstallationInfo,
    MetricsBatch,
    RegisterSnapshot,
    TelemetryLevel,
)


class TestTelemetryLevel:
    """Tests for TelemetryLevel enum."""

    def test_values(self):
        """Verify enum members have expected string values."""
        assert TelemetryLevel.OFF.value == "off"
        assert TelemetryLevel.ON.value == "on"

    def test_from_string(self):
        """Verify enum can be constructed from string values."""
        assert TelemetryLevel("off") == TelemetryLevel.OFF
        assert TelemetryLevel("on") == TelemetryLevel.ON


class TestInstallationInfo:
    """Tests for InstallationInfo dataclass."""

    def _make_info(self, **overrides):
        """Create an InstallationInfo with sensible defaults and optional overrides."""
        defaults = {
            "instance_hash": "abc123",
            "device_hash": "b" * 64,
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


class TestDeviceHashInPayloads:
    """Every payload type carries both identities (#395)."""

    def test_installation_emits_both_hashes(self):
        """Installation payload carries instance_hash and device_hash."""
        info = InstallationInfo(
            instance_hash="a" * 64,
            device_hash="b" * 64,
            profile="yutaki_s80",
            gateway_type="modbus_atw_mbs_02",
            ha_version="2026.8.0",
            integration_version="2.2.0",
            power_supply="single",
            has_dhw=True,
            has_pool=False,
            has_cooling=True,
            max_circuits=2,
            has_secondary_compressor=True,
        )
        payload = info.to_dict()
        assert payload["instance_hash"] == "a" * 64
        assert payload["device_hash"] == "b" * 64

    def test_metrics_emits_both_hashes(self):
        """Metrics batch carries instance_hash and device_hash."""
        payload = MetricsBatch(
            instance_hash="a" * 64,
            device_hash="b" * 64,
            points=[{"time": datetime(2026, 8, 15, tzinfo=UTC), "outdoor_temp": 5.0}],
        ).to_dict()
        assert payload["instance_hash"] == "a" * 64
        assert payload["device_hash"] == "b" * 64

    def test_snapshot_emits_both_hashes(self):
        """Register snapshot carries instance_hash and device_hash."""
        payload = RegisterSnapshot(
            instance_hash="a" * 64,
            device_hash="b" * 64,
            time=datetime(2026, 8, 15, tzinfo=UTC),
            profile="yutaki_s80",
            gateway_type="modbus_atw_mbs_02",
            registers={"outdoor_temp": 5.0},
        ).to_dict()
        assert payload["instance_hash"] == "a" * 64
        assert payload["device_hash"] == "b" * 64


class TestMetricsBatch:
    """Tests for MetricsBatch dataclass."""

    def test_to_dict_basic(self):
        """Verify batch serializes dict points correctly."""
        point = {"time": "2026-03-31T12:00:00+00:00", "outdoor_temp": 5.5}
        batch = MetricsBatch(
            instance_hash="abc123", device_hash="b" * 64, points=[point]
        )
        result = batch.to_dict()
        assert result["type"] == "metrics"
        assert result["instance_hash"] == "abc123"
        assert len(result["points"]) == 1
        assert result["points"][0]["outdoor_temp"] == 5.5

    def test_to_dict_converts_datetime(self):
        """Verify datetime objects in points are converted to ISO strings."""
        point = {"time": datetime(2026, 3, 31, 12, 0, tzinfo=UTC), "outdoor_temp": 5.5}
        batch = MetricsBatch(instance_hash="abc", device_hash="b" * 64, points=[point])
        result = batch.to_dict()
        assert isinstance(result["points"][0]["time"], str)

    def test_empty_batch(self):
        """Verify an empty batch serializes with an empty points list."""
        batch = MetricsBatch(instance_hash="abc", device_hash="b" * 64)
        result = batch.to_dict()
        assert result["points"] == []


class TestRegisterSnapshot:
    """Tests for RegisterSnapshot dataclass."""

    def test_creation_and_serialization(self):
        """Verify snapshot serializes with type, profile, and register data."""
        snapshot = RegisterSnapshot(
            instance_hash="abc123",
            device_hash="b" * 64,
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


class TestOldWorkerCompatibility:
    """A new client must stay safe against an un-upgraded Worker (#395).

    The two sides deploy independently. An old Worker validates by copying
    known fields into a fresh object, so a `device_hash` at the *top level* is
    dropped and the payload is accepted under the legacy identity. Nested
    inside `data`, or inside each metrics point, it would be stripped by the
    same whitelist or rejected by the point type check, and the compatibility
    claim would quietly stop holding. Presence tests alone do not catch a move,
    so placement is what is pinned here.
    """

    def _payloads(self) -> dict[str, dict]:
        now = datetime.now(tz=UTC)
        return {
            "installation": InstallationInfo(
                instance_hash="a" * 64,
                device_hash="b" * 64,
                profile="yutaki_s80",
                gateway_type="modbus_atw_mbs_02",
                ha_version="2026.8.0",
                integration_version="2.2.0",
                power_supply="single",
                has_dhw=True,
                has_pool=False,
                has_cooling=True,
                max_circuits=2,
                has_secondary_compressor=True,
            ).to_dict(),
            "metrics": MetricsBatch(
                instance_hash="a" * 64,
                device_hash="b" * 64,
                points=[{"time": now, "outdoor_temp": 5.0}],
            ).to_dict(),
            "snapshot": RegisterSnapshot(
                instance_hash="a" * 64,
                device_hash="b" * 64,
                time=now,
                profile="yutaki_s80",
                gateway_type="modbus_atw_mbs_02",
                registers={"outdoor_temp": 5},
            ).to_dict(),
        }

    def test_device_hash_sits_beside_instance_hash(self):
        """Top level, exactly where the legacy field lives."""
        for name, payload in self._payloads().items():
            assert payload["device_hash"] == "b" * 64, name
            assert payload["instance_hash"] == "a" * 64, name

    def test_device_hash_is_not_nested_in_the_installation_data(self):
        """An old Worker's whitelist would strip it and change nothing else."""
        assert "device_hash" not in self._payloads()["installation"]["data"]

    def test_device_hash_is_not_repeated_in_each_metrics_point(self):
        """A point carrying it would bloat the batch and hit the point checks."""
        for point in self._payloads()["metrics"]["points"]:
            assert "device_hash" not in point

    def test_dropping_device_hash_leaves_a_valid_legacy_payload(self):
        """What an old Worker sees must be exactly the pre-#395 shape."""
        for name, payload in self._payloads().items():
            legacy = {k: v for k, v in payload.items() if k != "device_hash"}
            assert legacy["type"] == name
            assert legacy["instance_hash"] == "a" * 64
            assert "device_hash" not in legacy
