"""Anonymization utilities for telemetry data."""

from __future__ import annotations

from dataclasses import replace
import hashlib
from typing import Any

from .models import InstallationInfo


def hash_instance_id(instance_id: str) -> str:
    """Hash an HA instance ID with SHA-256 (non-reversible)."""
    return hashlib.sha256(instance_id.encode()).hexdigest()


def round_temperature(value: float | None, precision: float = 0.5) -> float | None:
    """Round a temperature to the nearest increment (default 0.5°C).

    Prevents fingerprinting via overly precise temperature values.
    Returns None if input is None.
    """
    if value is None:
        return None
    return round(value / precision) * precision


def round_coordinate(value: float | None, precision: float = 1.0) -> float | None:
    """Round a geographic coordinate to the nearest degree (default 1°).

    1° ≈ 110 km — enough for climate region, too coarse to identify a city.
    Returns None if input is None.
    """
    if value is None:
        return None
    return round(value / precision) * precision


def anonymize_installation_info(info: InstallationInfo) -> InstallationInfo:
    """Anonymize InstallationInfo by rounding geographic coordinates."""
    return replace(
        info,
        latitude=round_coordinate(info.latitude),
        longitude=round_coordinate(info.longitude),
    )


# COP quality/metadata keys that should NOT be rounded
_COP_METADATA_SUFFIXES = ("_quality", "_measurements", "_time_span_minutes")


def anonymize_point(point: dict[str, Any]) -> dict[str, Any]:
    """Anonymize a telemetry data point by rounding sensitive values.

    Rules (applied by key pattern):
    - Keys containing '_temp': round to 0.5°C
    - Keys starting with 'cop_' (excluding quality/measurements/time_span): round to 1 decimal
    - 'water_flow': round to 1 decimal
    - 'thermal_power_*', 'electrical_power': round to 2 decimals

    Returns a new dict (does not mutate the original).
    """
    result: dict[str, Any] = {}
    for key, value in point.items():
        if value is None or not isinstance(value, (int, float)):
            result[key] = value
            continue

        if "_temp" in key:
            result[key] = round_temperature(value)
        elif (
            key.startswith("cop_")
            and not key.endswith(_COP_METADATA_SUFFIXES)
            or key == "water_flow"
        ):
            result[key] = round(value, 1)
        elif key.startswith("thermal_power") or key == "electrical_power":
            result[key] = round(value, 2)
        else:
            result[key] = value

    return result
