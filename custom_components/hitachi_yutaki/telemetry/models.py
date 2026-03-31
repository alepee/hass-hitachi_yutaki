"""Telemetry data models for anonymous data collection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TelemetryLevel(Enum):
    """User consent level for telemetry data collection."""

    OFF = "off"
    ON = "on"


@dataclass(frozen=True)
class InstallationInfo:
    """Anonymous installation snapshot sent daily.

    Identifies the heat pump model and capabilities without any
    personal data. Instance is identified only by a SHA-256 hash.
    """

    instance_hash: str
    profile: str
    gateway_type: str
    ha_version: str
    integration_version: str
    power_supply: str  # "single" or "three"
    has_dhw: bool
    has_pool: bool
    has_cooling: bool
    max_circuits: int
    has_secondary_compressor: bool
    latitude: float | None = None
    longitude: float | None = None
    climate_zone: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dict for JSON payload."""
        data: dict = {
            "profile": self.profile,
            "gateway_type": self.gateway_type,
            "ha_version": self.ha_version,
            "integration_version": self.integration_version,
            "power_supply": self.power_supply,
            "has_dhw": self.has_dhw,
            "has_pool": self.has_pool,
            "has_cooling": self.has_cooling,
            "max_circuits": self.max_circuits,
            "has_secondary_compressor": self.has_secondary_compressor,
        }
        if self.latitude is not None:
            data["latitude"] = self.latitude
        if self.longitude is not None:
            data["longitude"] = self.longitude
        if self.climate_zone is not None:
            data["climate_zone"] = self.climate_zone
        return {
            "type": "installation",
            "instance_hash": self.instance_hash,
            "data": data,
        }


@dataclass(frozen=True)
class MetricsBatch:
    """A batch of metric data points for a single instance."""

    instance_hash: str
    points: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON payload."""
        serialized_points = []
        for point in self.points:
            p = dict(point)
            if isinstance(p.get("time"), datetime):
                p["time"] = p["time"].isoformat()
            serialized_points.append(p)
        return {
            "type": "metrics",
            "instance_hash": self.instance_hash,
            "points": serialized_points,
        }


@dataclass(frozen=True)
class RegisterSnapshot:
    """Raw Modbus register snapshot for test fixture generation (ON level)."""

    instance_hash: str
    time: datetime
    profile: str
    gateway_type: str
    registers: dict[str, float]

    def to_dict(self) -> dict:
        """Serialize to dict for JSON payload."""
        return {
            "type": "snapshot",
            "instance_hash": self.instance_hash,
            "time": self.time.isoformat(),
            "profile": self.profile,
            "gateway_type": self.gateway_type,
            "registers": self.registers,
        }
