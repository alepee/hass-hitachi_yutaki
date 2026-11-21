"""Per-cycle heat balance behind the short-cycling alert (#512).

The cycling detector says *that* a compressor short cycles; this module says
*why*, with the installation's own numbers. It applies a lumped energy balance
to each complete space-heating cycle:

- during the run the loop warms, because the unit produces ``P`` while the
  emitters absorb less;
- during the rest the loop cools, because the emitters alone draw on it;
- over the whole cycle the loop gives back what it stored, so the emitters
  absorb ``P * run / (run + rest)``, and the outlet swing ``dT`` implies an
  effective water mass ``P * tau / (c * dT)`` with
  ``tau = run * rest / (run + rest)``.

Medians over many cycles absorb the 1 K resolution of the water temperature
registers. Only cycles the unit ends itself (thermo-off: the water target is
reached) are measured; a room thermostat ending the demand does not saturate
the loop, so the balance does not apply. Defrosts, other regimes and data holes
discard the cycle in progress.

The rules were checked by replaying the telemetry archive (see
``docs/reference/cycling-monitoring.md``): volumes come out between ~20 and
~160 L and stay stable from one day to the next on a given unit.

Pure business logic, stdlib only.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from statistics import median
from typing import Any

from ..models.cycling import CyclingDiagnosis

C_WATER_J_PER_KG_K = 4186.0
KW_PER_M3H_K = 1.163  # 1 m3/h of water across 1 K, in kW

# A cycle is measured only when both halves last at least this long, the
# output is real and the swing rises above the 1 K register resolution.
MIN_PHASE_S = 60.0
MIN_OUTPUT_KW = 0.5
MIN_SWING_K = 1.0
MIN_DIAGNOSED_CYCLES = 4

# The first third of a run is the compressor ramping up: its output is not
# representative of the regime the loop settles into.
RAMP_SKIP_FRACTION = 1 / 3

# Frequency floor: the lowest frequency the unit sustains. Units that cannot
# modulate further down sit on one plateau (31 Hz on many Yutaki), with ramp
# samples scattered below it as the compressor slows before a stop, so a low
# percentile lands under the plateau. The floor is instead the most populated
# 1 Hz bin of the lower half of the day's settled run samples. A run sample at
# most FLOOR_MARGIN_HZ above it counts as "at the floor".
FLOOR_MARGIN_HZ = 2.0

# Days the installation-level diagnosis is drawn from.
DIAGNOSIS_DAYS = 7


@dataclass(frozen=True)
class CycleSample:
    """One poll inside a cycle."""

    inlet: float | None
    outlet: float | None
    target: float | None
    flow: float | None
    frequency: float | None
    secondary_running: bool | None
    thermo_off: bool | None = None


@dataclass(frozen=True)
class CycleMeasurement:
    """Heat balance inputs of one complete cycle."""

    run_s: float
    rest_s: float
    output_kw: float
    swing_k: float
    return_minus_target_k: float | None

    @property
    def load_ratio(self) -> float:
        """Share of the unit's output the emitters absorb."""
        return self.run_s / (self.run_s + self.rest_s)

    @property
    def loop_volume_l(self) -> float:
        """Effective water volume implied by the swing, in litres (kg)."""
        tau = self.run_s * self.rest_s / (self.run_s + self.rest_s)
        return self.output_kw * 1000 * tau / (C_WATER_J_PER_KG_K * self.swing_k)


def _settled(samples: list[CycleSample]) -> list[CycleSample]:
    """Drop the ramp-up part of a run."""
    return samples[int(len(samples) * RAMP_SKIP_FRACTION) :]


def _thermal_kw(sample: CycleSample) -> float | None:
    """Return the instantaneous thermal output of one run sample."""
    if not sample.flow or sample.inlet is None or sample.outlet is None:
        return None
    return sample.flow * (sample.outlet - sample.inlet) * KW_PER_M3H_K


def measure_cycle(
    run: list[CycleSample],
    rest: list[CycleSample],
    *,
    run_s: float,
    rest_s: float,
    stop: CycleSample | None,
) -> CycleMeasurement | None:
    """Measure one complete cycle, or return None when it is not measurable."""
    if run_s < MIN_PHASE_S or rest_s < MIN_PHASE_S:
        return None

    powers = [p for s in _settled(run) if (p := _thermal_kw(s)) is not None]
    outlets_run = [s.outlet for s in run if s.outlet is not None]
    outlets_rest = [s.outlet for s in rest if s.outlet is not None]
    if not powers or not outlets_run or not outlets_rest:
        return None

    output = median(powers)
    swing = max(outlets_run) - min(outlets_rest)
    if output <= MIN_OUTPUT_KW or swing < MIN_SWING_K:
        return None

    return_minus_target = None
    if stop is not None and stop.inlet is not None and stop.target is not None:
        return_minus_target = stop.inlet - stop.target

    return CycleMeasurement(
        run_s=run_s,
        rest_s=rest_s,
        output_kw=output,
        swing_k=swing,
        return_minus_target_k=return_minus_target,
    )


@dataclass
class DailyCycleLog:
    """Measured cycles and settled run samples of the running day."""

    cycles: list[CycleMeasurement] = field(default_factory=list)
    frequencies: list[float] = field(default_factory=list)
    secondary: list[bool] = field(default_factory=list)
    secondary_targets: list[float] = field(default_factory=list)

    def add_run(self, run: list[CycleSample]) -> None:
        """Record the settled samples of a heating run (measured or not)."""
        for sample in _settled(run):
            if sample.frequency is not None and sample.frequency > 0:
                self.frequencies.append(sample.frequency)
            if sample.secondary_running is not None:
                self.secondary.append(sample.secondary_running)
                if sample.secondary_running and sample.target is not None:
                    self.secondary_targets.append(sample.target)

    def diagnose(self) -> CyclingDiagnosis | None:
        """Summarise the day, or return None below the cycle minimum."""
        cycles = self.cycles
        if len(cycles) < MIN_DIAGNOSED_CYCLES:
            return None

        output = median(c.output_kw for c in cycles)
        load = median(c.load_ratio for c in cycles)
        gaps = [
            c.return_minus_target_k
            for c in cycles
            if c.return_minus_target_k is not None
        ]
        return CyclingDiagnosis(
            cycles=len(cycles),
            output_kw=output,
            absorbed_kw=output * load,
            load_ratio=load,
            loop_volume_l=median(c.loop_volume_l for c in cycles),
            run_min=median(c.run_s for c in cycles) / 60,
            rest_min=median(c.rest_s for c in cycles) / 60,
            swing_k=median(c.swing_k for c in cycles),
            floor_share=_floor_share(self.frequencies),
            return_minus_target_k=median(gaps) if gaps else None,
            secondary_share=(
                sum(self.secondary) / len(self.secondary) if self.secondary else None
            ),
            secondary_target_c=(
                median(self.secondary_targets) if self.secondary_targets else None
            ),
        )


def _floor_share(frequencies: list[float]) -> float | None:
    """Return the share of settled run samples at the frequency floor."""
    if not frequencies:
        return None
    ordered = sorted(frequencies)
    lower_half = ordered[: max(1, len(ordered) // 2)]
    bins = Counter(round(f) for f in lower_half)
    floor = max(bins.items(), key=lambda item: (item[1], -item[0]))[0]
    at_floor = sum(1 for f in ordered if f <= floor + FLOOR_MARGIN_HZ)
    return at_floor / len(ordered)


def _median_optional(values: list[float | None]) -> float | None:
    """Return the median of the known values, or None."""
    known = [v for v in values if v is not None]
    return median(known) if known else None


def combine_diagnoses(days: list[CyclingDiagnosis]) -> CyclingDiagnosis | None:
    """Merge daily diagnoses into one installation-level picture.

    Each field is the median of the daily medians, so one atypical day (a cold
    snap, a holiday with the valves closed) does not swing the advice.
    """
    if not days:
        return None
    output = median(d.output_kw for d in days)
    load = median(d.load_ratio for d in days)
    return CyclingDiagnosis(
        cycles=sum(d.cycles for d in days),
        output_kw=output,
        absorbed_kw=median(d.absorbed_kw for d in days),
        load_ratio=load,
        loop_volume_l=median(d.loop_volume_l for d in days),
        run_min=median(d.run_min for d in days),
        rest_min=median(d.rest_min for d in days),
        swing_k=median(d.swing_k for d in days),
        floor_share=_median_optional([d.floor_share for d in days]),
        return_minus_target_k=_median_optional([d.return_minus_target_k for d in days]),
        secondary_share=_median_optional([d.secondary_share for d in days]),
        secondary_target_c=_median_optional([d.secondary_target_c for d in days]),
    )


def diagnosis_to_dict(diagnosis: CyclingDiagnosis) -> dict[str, float | int | None]:
    """Serialize a diagnosis for persistence."""
    return {
        "cycles": diagnosis.cycles,
        "output_kw": diagnosis.output_kw,
        "absorbed_kw": diagnosis.absorbed_kw,
        "load_ratio": diagnosis.load_ratio,
        "loop_volume_l": diagnosis.loop_volume_l,
        "run_min": diagnosis.run_min,
        "rest_min": diagnosis.rest_min,
        "swing_k": diagnosis.swing_k,
        "floor_share": diagnosis.floor_share,
        "return_minus_target_k": diagnosis.return_minus_target_k,
        "secondary_share": diagnosis.secondary_share,
        "secondary_target_c": diagnosis.secondary_target_c,
    }


def _opt_float(value: Any) -> float | None:
    """Parse an optional float, raising on anything else than None or a number."""
    if value is None:
        return None
    return float(value)


def diagnosis_from_dict(item: dict[str, Any]) -> CyclingDiagnosis:
    """Parse a persisted diagnosis; raises KeyError/TypeError/ValueError."""
    return CyclingDiagnosis(
        cycles=int(item["cycles"]),
        output_kw=float(item["output_kw"]),
        absorbed_kw=float(item["absorbed_kw"]),
        load_ratio=float(item["load_ratio"]),
        loop_volume_l=float(item["loop_volume_l"]),
        run_min=float(item["run_min"]),
        rest_min=float(item["rest_min"]),
        swing_k=float(item["swing_k"]),
        floor_share=_opt_float(item.get("floor_share")),
        return_minus_target_k=_opt_float(item.get("return_minus_target_k")),
        secondary_share=_opt_float(item.get("secondary_share")),
        secondary_target_c=_opt_float(item.get("secondary_target_c")),
    )
