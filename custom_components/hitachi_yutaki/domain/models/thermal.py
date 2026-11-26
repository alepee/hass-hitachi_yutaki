"""Thermal domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

DELTA_T_DEADBAND = 0.5
"""Smallest water ΔT, in K, that establishes a direction of heat transfer.

Inside this band the inlet and outlet thermistors cannot tell a real flow of
heat from their own offset and noise.
"""


class ThermalDirection(StrEnum):
    """Direction of heat transfer shown by the water ΔT."""

    HEATING = "heating"
    COOLING = "cooling"
    UNKNOWN = "unknown"
    """No reading, or a ΔT inside the deadband: the direction is not known."""


def thermal_direction(delta_t: float | None) -> ThermalDirection:
    """Classify a water ΔT (outlet minus inlet), honoring the deadband."""
    if delta_t is None or abs(delta_t) <= DELTA_T_DEADBAND:
        return ThermalDirection.UNKNOWN
    return ThermalDirection.HEATING if delta_t > 0 else ThermalDirection.COOLING


@dataclass
class ThermalPowerInput:
    """Input data for thermal power calculation."""

    water_inlet_temp: float  # °C
    water_outlet_temp: float  # °C
    water_flow: float  # m³/h
    is_defrosting: bool = False  # True if heat pump is in defrost mode


@dataclass
class ThermalEnergyResult:
    """Result of thermal energy calculation."""

    thermal_power: float  # kW
    daily_energy: float  # kWh
    total_energy: float  # kWh
    delta_t: float  # °C
    last_update: datetime
    last_reset_date: datetime
    daily_start_time: datetime | None
