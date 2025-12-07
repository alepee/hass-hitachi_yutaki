"""COP domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple


class PowerMeasurement(NamedTuple):
    """A power measurement with thermal and electrical components."""

    timestamp: datetime
    thermal_power: float  # kW
    electrical_power: float  # kW


@dataclass
class COPInput:
    """Input data for COP calculation."""

    water_inlet_temp: float | None
    water_outlet_temp: float | None
    water_flow: float | None
    compressor_current: float | None
    compressor_frequency: float | None
    secondary_compressor_current: float | None = None
    secondary_compressor_frequency: float | None = None
    hvac_action: str | None = None  # "heating", "cooling", or None


@dataclass
class COPQuality:
    """Quality indicator for COP measurements.

    Attributes:
        quality: Quality level (excellent/good/fair/poor/insufficient)
        measurements: Number of measurements used
        time_span_minutes: Time span covered by measurements

    """

    quality: str
    measurements: int
    time_span_minutes: float
