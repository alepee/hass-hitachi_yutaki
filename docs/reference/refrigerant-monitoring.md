# Refrigerant-circuit anomaly detection

**Status:** iteration 1 (slow refrigerant loss).
**Issue:** [#310](https://github.com/alepee/hass-hitachi_yutaki/issues/310).

This feature continuously watches the refrigerant circuit for the early signature of a
**slow refrigerant charge loss**, using the same physical quantities a technician samples
during a leak-tightness inspection, but sampled on every poll of your own installation.

> **It is advisory only.** It **complements** and does **not** replace the mandatory,
> periodic F-Gas leak-tightness inspection by a certified technician.

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

- **Suction superheat** `SH = Tg − Te` (`compressor_tg_gas_temp` −
  `compressor_te_evaporator_temp`).
- **Outdoor expansion-valve opening** `EVO`
  (`compressor_evo_outdoor_expansion_valve_opening`, 0–100 %).
- **Evaporating temperature** `Te` and **outdoor temperature** for context.

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
