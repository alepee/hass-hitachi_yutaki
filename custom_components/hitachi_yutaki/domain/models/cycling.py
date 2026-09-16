"""Compressor short-cycling detection domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import NamedTuple


@dataclass
class CyclingInput:
    """One poll's worth of compressor cycling signals.

    ``compressor_running`` is the state the transition detector tracks;
    ``operation_mode`` gates the regime (space heating only, see the service
    docstring). ``data_reliable`` mirrors the defrost guard: a defrost stops
    and restarts the compressor for reasons that have nothing to do with
    cycling, so those transitions must not be counted.
    """

    operation_mode: str | None
    compressor_running: bool | None
    data_reliable: bool = True


class CyclingDailyAggregate(NamedTuple):
    """Per-day summary of space-heating compressor cycles."""

    day: date
    cycles: int
    median_period: float  # minutes, median cycle period (start to next start)
    peak_starts: int  # highest start count over any 60-minute window
    median_run: float  # minutes, median run duration
    faulted: bool  # both criteria met on this day


@dataclass
class CyclingStatus:
    """Current detector verdict, surfaced to the diagnostic entity."""

    status: str  # learning / ok / watch / alert
    cycles_today: int
    peak_starts_today: int | None
    median_period_today: float | None
    median_run_today: float | None
    valid_days: int
    alert_streak: int
    last_valid_day: date | None = None
    days_since_valid_day: int | None = None
