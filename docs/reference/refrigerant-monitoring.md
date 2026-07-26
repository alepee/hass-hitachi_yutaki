# Refrigerant-circuit anomaly detection

**Status:** iteration 2 (beta): per-profile gas-line superheat plausibility bounds.
**Issue:** [#310](https://github.com/alepee/hass-hitachi_yutaki/issues/310),
[#393](https://github.com/alepee/hass-hitachi_yutaki/issues/393).

This feature continuously watches the refrigerant circuit for the early signature of a
**slow refrigerant charge loss**, using the same physical quantities a technician samples
during a leak-tightness inspection, but sampled on every poll of your own installation.

> **It is advisory only.** It **complements** and does **not** replace the mandatory,
> periodic F-Gas leak-tightness inspection by a certified technician.

> **This detection is in test (beta).** It will likely stay so for at least 1 to 2 years.
> Validating it needs cross-season fleet data (including winters) from a still-small fleet,
> so the thresholds and plausibility bounds will be recalibrated as more data arrives
> (see `backend/analysis/`, next winter re-run Jan-Feb 2027). Treat every verdict as an
> early-warning hint, not a measurement of charge.

## Opt-in and consent (beta)

This detection is **opt-in and off by default** (`CONF_REFRIGERANT_DETECTION`,
default `False`). The toggle lives in an **"Advanced features (beta)"** panel whose
first (currently only) feature is the refrigerant detection. Because it is beta,
nothing runs until you explicitly enable it:

- **During setup (install)**: on a profile that exposes the extended compressor
  sensors, the "Advanced features (beta)" panel is the last step before the entry is
  created. Leave the toggle off to keep everything disabled.
- **Later, via the integration Options** (the cog on the integration entry): the same
  panel lets you turn it on or off at any time, just before the telemetry step.
- **For existing installations**: an onboarding repair issue ("Try refrigerant charge
  monitoring (beta)") invites you to enable it. Its fix flow shows the same panel and
  writes your choice. It is created only on capable profiles and only until you have
  made a choice.

The panel is only offered on profiles with extended compressor sensors (so **never on
the Yutampo R32**, which cannot report the required signals). When the toggle is off,
the detector is not built, no baseline `Store` is created or restored, and none of its
entities (the `Refrigerant Charge Status` sensor, the `Reset Refrigerant Baseline`
button) or its repair issue exist.

The feature is beta and currently rests on very little validation data. It will only
be considered stable after a full winter heating season of cross-season validation, so
its verdicts may be unreliable until then. **Treat any alert as a hint to look closer,
not a diagnosis**: it can be a false positive, so double-check before calling a
technician or paying for a service. Enabling [anonymous telemetry](telemetry.md) helps
validate the detector across the whole fleet and reach a stable release sooner.

## What it surfaces

| Entity | Type | Notes |
|---|---|---|
| `sensor.*_refrigerant_charge_status` | ENUM diagnostic | `learning` / `ok` / `watch` / `alert`, on the Primary Compressor device |
| `button.*_reset_refrigerant_baseline` | button (config) | resets the learned baseline after a service/top-up |
| repair issue `refrigerant_charge_alert_*` | fixable warning | raised when `alert` persists several valid days; annotated as stale off-season, cleared in-season on recovery or by confirming a service |

The sensor exposes attributes: `superheat_delta` (K), `exv_delta` (%, `null` when it cannot
be compared at equivalent outdoor temperature), `evaporation_temp_delta` (K, informational),
`baseline_days`, `valid_days`, `alert_streak`, `last_valid_day` (ISO date of the most recent
qualifying day, `null` before any) and `days_since_valid_data` (calendar age of that day,
`null` until the first poll after a restart).

Only profiles with `supports_extended_compressor_sensors` (i.e. all except the Yutampo R32)
expose these, because the detector needs the gas temperature `Tg` and the outdoor expansion
valve `EVO`, which the compact Yutampo R32 does not report.

## How it works

The detector lives in the domain layer (`domain/services/refrigerant.py`, class
`RefrigerantMonitor`) and is driven by the coordinator adapter on each poll.

### Signals

- **Gas-line superheat** `SH = Tg − Te` (`compressor_tg_gas_temp` −
  `compressor_te_evaporator_temp`). `Tg` (register 1206) is the **THMg gas-pipe
  thermistor**, not a suction sensor, so in heating this `SH` is a condensing-side lift of
  ~40-60 K rather than a classic suction superheat. Detection compares drifts against the
  learned per-installation baseline, so this labelling detail does not change the behaviour.
- **Outdoor expansion-valve opening** `EVO`
  (`compressor_evo_outdoor_expansion_valve_opening`, 0–100 %).
- **Evaporating temperature** `Te` and **outdoor temperature** for context.

The per-poll plausibility bounds for `SH` are supplied by the active heat-pump profile
(`gas_superheat_plausible_range`, all `(-10, 80)` K provisionally), so the profiles remain
the single source of truth. When a freshly frozen baseline falls outside its model's
observed fleet band (`gas_superheat_observed_band`), a diagnostic warning is logged; it does
not affect detection and only flags a likely profile misdetection, a faulty sensor, or a
multi-unit HC-A(16/64)MB topology where `Tg` and `Te`/`EVO` describe different circuits.

### Sampling gate

A sample is recorded only when the poll is trustworthy and comparable: **heating mode**
(the outdoor coil is the evaporator, so `EVO` is the regulating valve), data reliable (the
defrost guard is not filtering), compressor frequency in a steady band, all signals present
and plausible, and at most one sample per minute. DHW and pool cycles are excluded by
construction (distinct operation modes).

### Baseline and detection

Samples are reduced to one robust **daily aggregate** (medians). After 14 valid days a
**baseline is frozen**. The last few valid days form a **recent window** compared to the
baseline:

- **Superheat** is the primary signal. It is a *regulated* quantity: a healthy circuit
  holds it in a stable band regardless of the weather, so a sustained rise is meaningful.
- **EVO** corroborates, but only over recent days whose outdoor temperature is within a few
  kelvin of the baseline's — because valve position genuinely moves with outdoor
  temperature, comparing unlike conditions would be misleading.
- **Te** is reported for information only; it is too weather-dependent to gate on.

| Status | Meaning |
|---|---|
| `learning` | Not enough history yet (warm-up). |
| `ok` | Baseline established, no significant drift. |
| `watch` | Superheat has drifted up from the baseline. |
| `alert` | Superheat **and** temperature-matched EVO opening have both drifted up — the classic slow-leak signature. |

When `alert` persists for several valid days a repair issue is raised. In season it clears
automatically as soon as the readings recover. Note that `ALERT_PERSIST_DAYS` counts *valid*
days (days with qualifying heating operation), not calendar days.

### Off-season behaviour

Off the heating season no day qualifies, so the recent window stops refreshing and the
verdict, the alert streak and the repair issue **freeze on the last valid data**. This is
intentional: a slow refrigerant loss does not repair itself over summer, so a real alert must
not silently self-clear.

To keep this honest rather than misleading, the data age is exposed:

- the `last_valid_day` and `days_since_valid_data` sensor attributes report how old the
  verdict is;
- beyond `STALE_AFTER_DAYS` (7 calendar days) the repair issue switches to a dedicated
  **stale** text that states the verdict is based on old data and why it is kept.

The user has two equivalent exits, both resetting the baseline (detector back to `learning`):

- the repair issue's **Fix** button, a "circuit was serviced" confirmation;
- the **Reset Refrigerant Baseline** button.

Only confirm/reset after a legitimate refrigerant top-up or expansion-valve service.

### Persistence and reset

The baseline and daily aggregates are persisted (Home Assistant `Store`) so they survive
restarts and build up over weeks, independent of whether the diagnostic entity is enabled.
After a **legitimate refrigerant top-up or expansion-valve service**, press **Reset
Refrigerant Baseline** so a fresh reference is learned; otherwise the stale baseline would
keep alerting.

The snapshot is restored **before** the first poll after a restart, so an established alert
(and its repair issue) survives a Home Assistant restart without flapping to `learning` for
one poll cycle. A corrupt snapshot is validated when it is loaded, discarded with a logged
warning (the restore is atomic, so partial state can never be applied), and the detector
restarts in `learning`.

The `Store` (`.storage/hitachi_yutaki_refrigerant_<entry_id>`) is deleted automatically when
the config entry is removed (`async_remove_entry`), leaving no orphaned baseline behind.

## Limitations (expected)

- **Warm-up:** needs ~2–3 weeks of heating operation before it can leave `learning`. Off
  season it stays `learning`.
- **Heating only** in this iteration; cooling-dominant installs won't accumulate data.
- **Heuristic thresholds:** false positives are possible on unusual load patterns. The
  superheat-primary rule, the temperature-matched EVO check and daily medians mitigate this,
  but the result is an early-warning hint, not a measurement of charge.
- **Coarse superheat:** temperatures are whole-degree integers, so superheat has ~1 K
  quantization; daily medians recover finer resolution.
- **Not available on the Yutampo R32** (no `Tg`/`EVO`).

## Tuning constants

All thresholds live at the top of `domain/services/refrigerant.py`
(`BASELINE_DAYS`, `EVAL_DAYS`, `MIN_SAMPLES_PER_DAY`, `SUPERHEAT_WATCH_K`,
`SUPERHEAT_ALERT_K`, `EVO_ALERT_PCT`, `TEMP_MATCH_K`, `ALERT_PERSIST_DAYS`,
`STALE_AFTER_DAYS`, …) and are covered by `tests/domain/services/test_refrigerant.py`.

The gas-line superheat **plausibility range** is no longer a module constant: it lives
per-profile as `gas_superheat_plausible_range` (all `(-10, 80)` K provisionally) and is
injected into the monitor at construction. The companion `gas_superheat_observed_band`
feeds the freeze-time off-band check. Both are declared in `profiles/` and will be
recalibrated per model after the next winter re-run of `backend/analysis/`.
