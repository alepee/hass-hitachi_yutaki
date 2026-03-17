"""Anonymization utilities for telemetry data."""

from __future__ import annotations

from dataclasses import replace
import hashlib

from .models import DailyStats, MetricPoint


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


def anonymize_metric_point(point: MetricPoint) -> MetricPoint:
    """Anonymize a MetricPoint by rounding all temperature fields."""
    return replace(
        point,
        outdoor_temp=round_temperature(point.outdoor_temp),
        water_inlet_temp=round_temperature(point.water_inlet_temp),
        water_outlet_temp=round_temperature(point.water_outlet_temp),
        dhw_temp=round_temperature(point.dhw_temp),
        circuit1_water_temp=round_temperature(point.circuit1_water_temp),
        circuit2_water_temp=round_temperature(point.circuit2_water_temp),
        # Round COP to 1 decimal place
        cop_instant=round(point.cop_instant, 1) if point.cop_instant is not None else None,
        # Round setpoint temperatures
        circuit1_target_temp=round_temperature(point.circuit1_target_temp),
        circuit2_target_temp=round_temperature(point.circuit2_target_temp),
        dhw_target_temp=round_temperature(point.dhw_target_temp),
        water_target_temp=round_temperature(point.water_target_temp),
        # Round water flow to 1 decimal
        water_flow=round(point.water_flow, 1) if point.water_flow is not None else None,
        # OTC max flow temps
        circuit1_max_flow_temp_heating=round_temperature(point.circuit1_max_flow_temp_heating),
        circuit1_max_flow_temp_cooling=round_temperature(point.circuit1_max_flow_temp_cooling),
        circuit2_max_flow_temp_heating=round_temperature(point.circuit2_max_flow_temp_heating),
        circuit2_max_flow_temp_cooling=round_temperature(point.circuit2_max_flow_temp_cooling),
        # Primary compressor temperatures
        compressor_tg_gas_temp=round_temperature(point.compressor_tg_gas_temp),
        compressor_ti_liquid_temp=round_temperature(point.compressor_ti_liquid_temp),
        compressor_td_discharge_temp=round_temperature(point.compressor_td_discharge_temp),
        compressor_te_evaporator_temp=round_temperature(point.compressor_te_evaporator_temp),
        # Secondary compressor temperatures
        secondary_compressor_discharge_temp=round_temperature(point.secondary_compressor_discharge_temp),
        secondary_compressor_suction_temp=round_temperature(point.secondary_compressor_suction_temp),
        # Additional temperatures
        water_outlet_2_temp=round_temperature(point.water_outlet_2_temp),
        water_outlet_3_temp=round_temperature(point.water_outlet_3_temp),
        pool_current_temp=round_temperature(point.pool_current_temp),
        pool_target_temp=round_temperature(point.pool_target_temp),
    )


def anonymize_daily_stats(stats: DailyStats) -> DailyStats:
    """Anonymize DailyStats by rounding temperature aggregates."""
    return replace(
        stats,
        outdoor_temp_min=round_temperature(stats.outdoor_temp_min),
        outdoor_temp_max=round_temperature(stats.outdoor_temp_max),
        outdoor_temp_avg=round_temperature(stats.outdoor_temp_avg),
        cop_avg=round(stats.cop_avg, 1) if stats.cop_avg is not None else None,
        cop_min=round(stats.cop_min, 1) if stats.cop_min is not None else None,
        cop_max=round(stats.cop_max, 1) if stats.cop_max is not None else None,
        # Round energy to 1 decimal
        thermal_energy_kwh=round(stats.thermal_energy_kwh, 1),
        electrical_energy_kwh=round(stats.electrical_energy_kwh, 1),
        # Round hours to 1 decimal
        compressor_hours=round(stats.compressor_hours, 1),
        defrost_total_minutes=round(stats.defrost_total_minutes, 1),
        heating_hours=round(stats.heating_hours, 1),
        cooling_hours=round(stats.cooling_hours, 1),
        dhw_hours=round(stats.dhw_hours, 1),
    )
