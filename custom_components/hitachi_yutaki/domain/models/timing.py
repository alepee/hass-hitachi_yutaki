"""Compressor timing domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompressorTimingResult:
    """Timing measurements for compressor cycles."""

    cycle_time: float | None  # minutes - time between starts
    runtime: float | None  # minutes - average run duration
    resttime: float | None  # minutes - average rest duration
