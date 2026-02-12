"""Electrical domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ElectricalPowerInput:
    """Input data for electrical power calculation."""

    current: float  # Amperes
    measured_power: float | None = None  # kW (if directly measured)
    voltage: float | None = None  # Volts
    is_three_phase: bool = False  # True for 3-phase, False for single-phase
