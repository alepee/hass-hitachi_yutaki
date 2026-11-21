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

    The remaining fields feed the per-cycle diagnostic (#512) and are all
    optional: without a water flow reading, cycles are still counted but no
    diagnostic is derived. ``thermo_off`` tells a stop decided by the unit
    (water target reached) from one decided by a room thermostat; only the
    former closes a cycle the heat balance applies to.
    """

    operation_mode: str | None
    compressor_running: bool | None
    data_reliable: bool = True
    thermo_off: bool | None = None
    water_inlet_temp: float | None = None
    water_outlet_temp: float | None = None
    water_target_temp: float | None = None
    water_flow: float | None = None  # m3/h
    compressor_frequency: float | None = None  # Hz
    secondary_compressor_running: bool | None = None


@dataclass(frozen=True)
class CyclingDiagnosis:
    """Heat balance of a set of short cycles (medians over the cycles).

    During a run the loop warms (the unit produces more than the emitters
    absorb); during the rest it cools (the emitters alone). Over a full cycle
    the loop gives back what it stored, so the emitters absorb
    ``output_kw * run / (run + rest)``, and the water mass that the observed
    temperature swing implies is the effective loop volume.
    """

    cycles: int  # cycles the medians are taken over
    output_kw: float  # thermal output while running
    absorbed_kw: float  # heat the emitters actually absorb
    load_ratio: float  # absorbed / output, i.e. run / (run + rest)
    loop_volume_l: float  # effective water volume of the loop
    run_min: float  # median run duration
    rest_min: float  # median rest duration
    swing_k: float  # median outlet swing over a cycle
    floor_share: float | None  # share of run time at the lowest frequency seen
    return_minus_target_k: float | None  # water inlet minus target at the stop
    secondary_share: float | None  # share of run time with the 2nd compressor on
    secondary_target_c: float | None  # median water target while it runs


class CyclingDailyAggregate(NamedTuple):
    """Per-day summary of space-heating compressor cycles."""

    day: date
    cycles: int
    median_period: float  # minutes, median cycle period (start to next start)
    peak_starts: int  # highest start count over any 60-minute window
    median_run: float  # minutes, median run duration
    faulted: bool  # both criteria met on this day
    diagnosis: CyclingDiagnosis | None = None  # heat balance, when measurable


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
    diagnosis: CyclingDiagnosis | None = None
    diagnosis_days: int = 0  # stored days the diagnosis is drawn from
