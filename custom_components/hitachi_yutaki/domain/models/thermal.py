"""Thermal domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


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
