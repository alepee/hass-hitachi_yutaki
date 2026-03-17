"""Telemetry data models for anonymous data collection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class TelemetryLevel(Enum):
    """User consent level for telemetry data collection."""

    OFF = "off"
    BASIC = "basic"
    FULL = "full"


@dataclass(frozen=True)
class InstallationInfo:
    """Anonymous installation snapshot sent daily (Basic + Full).

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

    def to_dict(self) -> dict:
        """Serialize to dict for JSON payload."""
        return {
            "type": "installation",
            "instance_hash": self.instance_hash,
            "data": {
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
            },
        }


@dataclass(frozen=True)
class MetricPoint:
    """A single telemetry metric sample (Full level, every poll cycle).

    All temperature fields are in °C (rounded to 0.5 by anonymizer).
    Power fields are in kW. Current in amps. Frequency in Hz.
    """

    time: datetime
    outdoor_temp: float | None = None
    water_inlet_temp: float | None = None
    water_outlet_temp: float | None = None
    dhw_temp: float | None = None
    compressor_on: bool | None = None
    compressor_frequency: float | None = None
    compressor_current: float | None = None
    thermal_power: float | None = None
    electrical_power: float | None = None
    cop_instant: float | None = None
    cop_quality: str | None = None
    unit_mode: str | None = None
    is_defrosting: bool | None = None
    dhw_active: bool | None = None
    circuit1_water_temp: float | None = None
    circuit2_water_temp: float | None = None
    # Setpoints and control state (for world model training)
    circuit1_target_temp: float | None = None
    circuit2_target_temp: float | None = None
    dhw_target_temp: float | None = None
    water_target_temp: float | None = None
    water_flow: float | None = None
    circuit1_otc_method_heating: str | None = None
    circuit1_otc_method_cooling: str | None = None
    circuit2_otc_method_heating: str | None = None
    circuit2_otc_method_cooling: str | None = None
    circuit1_eco_mode: bool | None = None
    circuit2_eco_mode: bool | None = None
    circuit1_power: bool | None = None
    circuit2_power: bool | None = None
    dhw_power: bool | None = None
    # OTC parameters
    circuit1_max_flow_temp_heating: float | None = None
    circuit1_max_flow_temp_cooling: float | None = None
    circuit1_heat_eco_offset: float | None = None
    circuit1_cool_eco_offset: float | None = None
    circuit2_max_flow_temp_heating: float | None = None
    circuit2_max_flow_temp_cooling: float | None = None
    circuit2_heat_eco_offset: float | None = None
    circuit2_cool_eco_offset: float | None = None
    # Primary compressor thermodynamics
    compressor_tg_gas_temp: float | None = None
    compressor_ti_liquid_temp: float | None = None
    compressor_td_discharge_temp: float | None = None
    compressor_te_evaporator_temp: float | None = None
    compressor_evi_valve_opening: float | None = None
    compressor_evo_valve_opening: float | None = None
    # Secondary compressor (S80 cascade)
    secondary_compressor_frequency: float | None = None
    secondary_compressor_discharge_temp: float | None = None
    secondary_compressor_suction_temp: float | None = None
    secondary_compressor_discharge_pressure: float | None = None
    secondary_compressor_suction_pressure: float | None = None
    secondary_compressor_valve_opening: float | None = None
    # System state
    unit_power: bool | None = None
    pump_speed: float | None = None
    operation_state_code: int | None = None
    alarm_code: int | None = None
    system_status: int | None = None
    # DHW modes
    dhw_boost: bool | None = None
    dhw_high_demand: bool | None = None
    # Additional temperatures
    water_outlet_2_temp: float | None = None
    water_outlet_3_temp: float | None = None
    pool_current_temp: float | None = None
    pool_target_temp: float | None = None

    def to_dict(self) -> dict:
        """Serialize to dict for JSON payload, omitting None values."""
        result: dict = {"time": self.time.isoformat()}
        for fld in (
            "outdoor_temp",
            "water_inlet_temp",
            "water_outlet_temp",
            "dhw_temp",
            "compressor_on",
            "compressor_frequency",
            "compressor_current",
            "thermal_power",
            "electrical_power",
            "cop_instant",
            "cop_quality",
            "unit_mode",
            "is_defrosting",
            "dhw_active",
            "circuit1_water_temp",
            "circuit2_water_temp",
            "circuit1_target_temp",
            "circuit2_target_temp",
            "dhw_target_temp",
            "water_target_temp",
            "water_flow",
            "circuit1_otc_method_heating",
            "circuit1_otc_method_cooling",
            "circuit2_otc_method_heating",
            "circuit2_otc_method_cooling",
            "circuit1_eco_mode",
            "circuit2_eco_mode",
            "circuit1_power",
            "circuit2_power",
            "dhw_power",
            "circuit1_max_flow_temp_heating",
            "circuit1_max_flow_temp_cooling",
            "circuit1_heat_eco_offset",
            "circuit1_cool_eco_offset",
            "circuit2_max_flow_temp_heating",
            "circuit2_max_flow_temp_cooling",
            "circuit2_heat_eco_offset",
            "circuit2_cool_eco_offset",
            "compressor_tg_gas_temp",
            "compressor_ti_liquid_temp",
            "compressor_td_discharge_temp",
            "compressor_te_evaporator_temp",
            "compressor_evi_valve_opening",
            "compressor_evo_valve_opening",
            "secondary_compressor_frequency",
            "secondary_compressor_discharge_temp",
            "secondary_compressor_suction_temp",
            "secondary_compressor_discharge_pressure",
            "secondary_compressor_suction_pressure",
            "secondary_compressor_valve_opening",
            "unit_power",
            "pump_speed",
            "operation_state_code",
            "alarm_code",
            "system_status",
            "dhw_boost",
            "dhw_high_demand",
            "water_outlet_2_temp",
            "water_outlet_3_temp",
            "pool_current_temp",
            "pool_target_temp",
        ):
            val = getattr(self, fld)
            if val is not None:
                result[fld] = val
        return result


@dataclass(frozen=True)
class MetricsBatch:
    """A batch of metric points for a single instance (Full level, sent every 5min)."""

    instance_hash: str
    points: list[MetricPoint] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON payload."""
        return {
            "type": "metrics",
            "instance_hash": self.instance_hash,
            "points": [p.to_dict() for p in self.points],
        }


@dataclass(frozen=True)
class DailyStats:
    """Daily aggregated statistics (Basic + Full, sent 1x/day)."""

    instance_hash: str
    date: date
    outdoor_temp_min: float | None = None
    outdoor_temp_max: float | None = None
    outdoor_temp_avg: float | None = None
    cop_avg: float | None = None
    cop_min: float | None = None
    cop_max: float | None = None
    cop_quality_best: str | None = None
    compressor_starts: int = 0
    compressor_hours: float = 0.0
    defrost_count: int = 0
    defrost_total_minutes: float = 0.0
    thermal_energy_kwh: float = 0.0
    electrical_energy_kwh: float = 0.0
    heating_hours: float = 0.0
    cooling_hours: float = 0.0
    dhw_hours: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to dict for JSON payload."""
        data = {}
        for fld in (
            "outdoor_temp_min",
            "outdoor_temp_max",
            "outdoor_temp_avg",
            "cop_avg",
            "cop_min",
            "cop_max",
            "cop_quality_best",
            "compressor_starts",
            "compressor_hours",
            "defrost_count",
            "defrost_total_minutes",
            "thermal_energy_kwh",
            "electrical_energy_kwh",
            "heating_hours",
            "cooling_hours",
            "dhw_hours",
        ):
            val = getattr(self, fld)
            if val is not None:
                data[fld] = val
        return {
            "type": "daily_stats",
            "instance_hash": self.instance_hash,
            "date": self.date.isoformat(),
            "data": data,
        }


@dataclass(frozen=True)
class RegisterSnapshot:
    """Raw Modbus register snapshot for test fixture generation (Full level)."""

    instance_hash: str
    time: datetime
    profile: str
    gateway_type: str
    registers: dict[str, int]

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
