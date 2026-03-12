"""Aggregation of telemetry metric points into daily statistics."""

from __future__ import annotations

from datetime import date

from .models import DailyStats, MetricPoint

# Unit mode string values (mapped from coordinator data)
_MODE_HEAT = "heat"
_MODE_COOL = "cool"

# Approximate poll interval in hours (5 seconds)
_POLL_INTERVAL_HOURS = 5.0 / 3600.0


def aggregate_metrics(
    instance_hash: str,
    stats_date: date,
    points: list[MetricPoint],
) -> DailyStats:
    """Aggregate a list of MetricPoints into a single DailyStats.

    Pure function — no side effects, no state. Computes min/max/avg
    for temperatures and COP, counts compressor starts, sums energy
    and mode hours from individual sample points.
    """
    if not points:
        return DailyStats(instance_hash=instance_hash, date=stats_date)

    # Collect non-None values for numeric aggregation
    outdoor_temps = [p.outdoor_temp for p in points if p.outdoor_temp is not None]
    cop_values = [p.cop_instant for p in points if p.cop_instant is not None]

    # Compressor starts: count False→True transitions
    compressor_starts = 0
    prev_compressor = None
    compressor_on_samples = 0
    for p in points:
        if p.compressor_on is not None:
            if prev_compressor is False and p.compressor_on is True:
                compressor_starts += 1
            if p.compressor_on:
                compressor_on_samples += 1
            prev_compressor = p.compressor_on

    # Defrost: count False→True transitions, sum True samples
    defrost_count = 0
    prev_defrost = None
    defrost_on_samples = 0
    for p in points:
        if p.is_defrosting is not None:
            if prev_defrost is False and p.is_defrosting is True:
                defrost_count += 1
            if p.is_defrosting:
                defrost_on_samples += 1
            prev_defrost = p.is_defrosting

    # Mode hours: count samples per mode
    heating_samples = 0
    cooling_samples = 0
    dhw_samples = 0
    for p in points:
        if p.unit_mode == _MODE_HEAT:
            heating_samples += 1
        elif p.unit_mode == _MODE_COOL:
            cooling_samples += 1
        if p.dhw_active:
            dhw_samples += 1

    # Energy: sum thermal and electrical power samples
    # Each sample represents ~5 seconds of operation
    thermal_power_values = [p.thermal_power for p in points if p.thermal_power is not None]
    electrical_power_values = [p.electrical_power for p in points if p.electrical_power is not None]

    # COP quality: pick the best quality level seen
    cop_quality_best = _best_cop_quality(points)

    return DailyStats(
        instance_hash=instance_hash,
        date=stats_date,
        outdoor_temp_min=min(outdoor_temps) if outdoor_temps else None,
        outdoor_temp_max=max(outdoor_temps) if outdoor_temps else None,
        outdoor_temp_avg=_avg(outdoor_temps),
        cop_avg=_avg(cop_values),
        cop_min=min(cop_values) if cop_values else None,
        cop_max=max(cop_values) if cop_values else None,
        cop_quality_best=cop_quality_best,
        compressor_starts=compressor_starts,
        compressor_hours=compressor_on_samples * _POLL_INTERVAL_HOURS,
        defrost_count=defrost_count,
        defrost_total_minutes=defrost_on_samples * _POLL_INTERVAL_HOURS * 60.0,
        thermal_energy_kwh=sum(thermal_power_values) * _POLL_INTERVAL_HOURS,
        electrical_energy_kwh=sum(electrical_power_values) * _POLL_INTERVAL_HOURS,
        heating_hours=heating_samples * _POLL_INTERVAL_HOURS,
        cooling_hours=cooling_samples * _POLL_INTERVAL_HOURS,
        dhw_hours=dhw_samples * _POLL_INTERVAL_HOURS,
    )


def _avg(values: list[float]) -> float | None:
    """Compute average, returning None for empty lists."""
    if not values:
        return None
    return sum(values) / len(values)


# Quality ordering from worst to best
_COP_QUALITY_ORDER = {
    "no_data": 0,
    "insufficient_data": 1,
    "preliminary": 2,
    "optimal": 3,
}


def _best_cop_quality(points: list[MetricPoint]) -> str | None:
    """Return the best COP quality level from a list of points."""
    best: str | None = None
    best_rank = -1
    for p in points:
        if p.cop_quality is not None:
            rank = _COP_QUALITY_ORDER.get(p.cop_quality, -1)
            if rank > best_rank:
                best = p.cop_quality
                best_rank = rank
    return best
