# Preventive maintenance detectors

**Status:** beta. Each detector is opt-in and off by default.

Preventive maintenance detectors run **locally**, on signals the heat pump already
reports, and warn about a problem while it is still cheap to fix. They are grouped in a
**"Preventive maintenance"** section of the **"Advanced features (beta)"** panel, with
**one consent toggle per detector**.

> **They are advisory.** A verdict is a hint to look closer, never a diagnosis. Do not
> call a technician or pay for a service on the strength of an alert alone.

## Available detectors

| Detector | Entity | Profiles | Warm-up | Reference |
|---|---|---|---|---|
| Refrigerant charge loss | `sensor.*_refrigerant_charge_status` | Extended compressor sensors (never Yutampo R32) | ~14 valid heating days | [refrigerant-monitoring.md](refrigerant-monitoring.md) |
| Compressor short cycling | `sensor.*_compressor_cycling` | All | 3 heating days | [cycling-monitoring.md](cycling-monitoring.md) |

## Why one toggle per detector

The detectors do not share a hardware scope, a warm-up time, or a failure mode:
refrigerant monitoring needs the extended compressor sensors and about two weeks of
heating before it says anything, while short-cycling detection works on any profile and
reaches a verdict in three days. A single global consent would switch on detections that
cannot apply to a given machine, and would make one detector's warm-up look like another
one's bug. Each toggle is therefore independent, and each is off until you turn it on.

Consent is stored flat in the entry options (`refrigerant_detection`,
`cycling_detection`). The config-flow *section* is a presentation device only: its values
are flattened on write, so the storage layout does not follow the shape of the form.

## Two detection patterns

Detectors fall into two families, and picking the wrong one makes a detector
structurally blind.

**Learned baseline, relative drift.** The detector observes *this* installation for a
warm-up window, freezes a reference, then watches the drift away from it. This is the
right pattern for a **slow degradation**, and the only workable one when the spread
between installations is too wide for an absolute threshold. Fleet evidence: up to 26 K
of inter-installation spread on gas-line superheat within a single model.

**Absolute threshold per regime.** No baseline at all. This is the right pattern when the
fault is a **stable state** rather than a drift: a baseline would learn the fault and
never report it. Fleet evidence for short cycling: the inter-unit over intra-unit
dispersion ratio is 3.3 in heating, so what separates a cycling installation from a
healthy one is not how it changed, it is what it is.

The question to ask of any new detector is therefore: *is this a drift, or a state?*

## Calibration

Thresholds are calibrated by replaying the anonymous telemetry archive rather than taken
from the literature, then checked for false-positive pressure across the fleet. A rule
that fires on a third of installations is worthless no matter how physically sound it is.
See `backend/analysis/` for the pipeline.

Two standing limitations apply to every detector calibrated so far:

- the archive starts in April 2026 and contains **no point below 0 °C outdoors**, so
  behaviour at full winter load is not validated (re-run planned for January-February
  2027);
- the consenting fleet grew over time, so comparing two periods also compares two
  populations.

Turning on [anonymous telemetry](telemetry.md) is what makes this calibration possible.
