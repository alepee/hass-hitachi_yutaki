"""Refrigerant-circuit anomaly detection domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import NamedTuple


@dataclass
class RefrigerantInput:
    """One poll's worth of refrigerant-circuit signals.

    All numeric fields are optional because the gateway may return ``None`` for
    a register (read error, sentinel, or 0xFFFF). ``data_reliable`` mirrors the
    defrost guard: the sample is only usable when the reading is trustworthy.
    """

    operation_mode: str | None
    compressor_frequency: float | None
    gas_temp: float | None  # Tg, suction gas temperature (°C)
    evaporator_temp: float | None  # Te, evaporating/saturation temperature (°C)
    outdoor_expansion_valve: float | None  # EVO opening (%)
    outdoor_temp: float | None  # outdoor ambient temperature (°C)
    data_reliable: bool = True


class DailyAggregate(NamedTuple):
    """Robust per-day summary of qualifying refrigerant samples."""

    day: date
    superheat: float  # median suction superheat Tg - Te (K)
    evaporation_temp: float  # median Te (°C)
    exv: float  # median EVO opening (%)
    outdoor_temp: float  # median outdoor ambient (°C)
    sample_count: int


@dataclass
class RefrigerantBaseline:
    """Frozen reference established from the first valid days."""

    superheat: float
    evaporation_temp: float
    exv: float
    outdoor_temp: float
    days: int


@dataclass
class RefrigerantStatus:
    """Current detector verdict, surfaced to the diagnostic entity."""

    status: str  # learning / ok / watch / alert
    superheat_delta: float | None
    exv_delta: float | None  # None when no temperature-matched recent days
    evaporation_temp_delta: float | None
    baseline: RefrigerantBaseline | None
    valid_days: int
    today_samples: int
    alert_streak: int
    last_valid_day: date | None = None
    days_since_valid_data: int | None = None
