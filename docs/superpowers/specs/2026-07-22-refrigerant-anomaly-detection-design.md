# Design: refrigerant-circuit anomaly detection (iteration 1)

**Issue:** [#310](https://github.com/alepee/hass-hitachi_yutaki/issues/310)
**Date:** 2026-07-22
**Scope:** first iteration — one local detector for *slow refrigerant loss*, a diagnostic
entity, a self-clearing repair issue, tests and docs.

---

## 1. Goal and non-goals

Surface early signs of a **slow refrigerant charge loss** between two mandatory F-Gas
leak-tightness inspections, using signals the integration already reads every poll. This
**complements** and does **not** replace the legal inspection.

**In scope (this PR):**

- One domain detector for slow refrigerant loss, running locally on rolling history.
- A diagnostic ENUM sensor `sensor.*_refrigerant_charge_status` with states
  `learning` / `ok` / `watch` / `alert` plus explanatory attributes.
- A self-clearing repair issue raised when `alert` persists over several days, with
  language making clear it complements the mandatory inspection.
- Unit tests (pure domain) and a documentation page.

**Out of scope (future iterations, tracked on #310):**

- EXV-hunting and heat-exchanger-fouling detectors, compressor-degradation detector.
- Fleet/telemetry-bootstrapped baselines (issue's "could help" section). Iteration 1 is
  strictly **local baselines**, as the issue recommends.
- Any actuation (compressor protection, shutdown). Strictly read-only / advisory.
- Quantitative refrigerant-charge estimation.
- Cooling-mode detection (heating only in iteration 1 — see §4).

---

## 2. Physical basis (why these signals)

A slow undercharge/leak has a classic thermodynamic signature at the evaporator:

- **Suction superheat rises.** Superheat `SH = Tg − Te` where `Tg` =
  `compressor_tg_gas_temp` (suction gas temperature) and `Te` =
  `compressor_te_evaporator_temp` (evaporating/saturation temperature). Less refrigerant →
  the evaporator dries out earlier → suction gas is hotter above saturation.
- **The expansion valve opens further to compensate.** `EVO` =
  `compressor_evo_outdoor_expansion_valve_opening` trends up as the EXV tries to restore
  superheat, until it saturates.
- **Evaporating temperature drifts down** (`Te` falls) at equivalent load.

Tracking **superheat and EXV opening is robust to seasonality** because superheat is a
*regulated* quantity: in a healthy circuit the EXV holds it in a stable band regardless of
outdoor temperature. A sustained joint drift (SH up **and** EVO up, Te not rising) is the
discriminating signal.

**Signal availability.** `Tg`, `EVI`, `EVO` are gated by the profile capability
`supports_extended_compressor_sensors` (only `YutampoR32Profile` sets it `False`). `Te`,
`Td`, frequency and current are always present. The detector therefore gates on
`supports_extended_compressor_sensors` — excluding the Yutampo R32, which lacks `Tg`/`EVO`.

---

## 3. Architecture (fits existing hexagonal layers)

```
Modbus data ──► DerivedMetricsAdapter.update(data)           [adapters/]
                   └─ RefrigerantMonitor.update(RefrigerantInput, timestamp)
                        │  (pure domain, no HA imports)       [domain/services/]
                        ▼
                   data["refrigerant_charge_status"] + attribute keys
                        ▼
   HitachiYutakiRefrigerantSensor  (ENUM, RestoreEntity)      [entities/compressor/]
        └─ persists/restores detector state via extra-data
   repairs / __init__: raise/clear repair issue on sustained alert
```

- **Domain stays pure** (stdlib only, `datetime`/`time`, no HA). Follows the COP pattern:
  optional `timestamp` kwarg for replay/tests, `time()` for the sample-interval throttle.
- Rolling history uses the existing `Storage[T]` port + `InMemoryStorage`, holding one
  compact `DailyAggregate` **per day** (not raw samples), so weeks of history cost ~45
  records. Intra-day samples live in a transient in-memory buffer.
- Wiring mirrors COP: instantiated in `DerivedMetricsAdapter.__init__`, driven by a new
  `_update_refrigerant(data)` inside `update()`, results written into the `data` dict.

### Persistence

Multi-week baselines cannot rely on Recorder replay (default purge ~10 days), nor on the
sensor's `RestoreEntity` state: a compound state (frozen baseline + up to ~45 daily
aggregates + alert streak) does not fit a single numeric `last_state`, and an entity that is
disabled in the registry never fires `async_added_to_hass`, so entity extra-data would be a
silent no-op. Instead the **adapter owns a `homeassistant.helpers.storage.Store`** (key
`hitachi_yutaki_refrigerant_{entry_id}`, versioned) holding the serialized detector state,
fully decoupled from entity enablement:

- Loaded once in `__init__.py async_setup_entry` (alongside the existing thermal/COP
  restores) and pushed into the service via `restore_refrigerant(state)`.
- Saved with `store.async_delay_save(monitor.serialize, ...)` on each daily flush (rare, so
  debounced I/O is negligible) and flushed on `async_unload_entry`.

The transient intra-day buffer is volatile (acceptable: at most the current partial day is
lost on restart). `Store` is standard HA infrastructure; the repo does not use it yet, but
it is the correct mechanism for compound, entity-independent persisted state.

---

## 4. Detector logic

### Sampling gate (a sample is recorded only when all hold)

- Operation mode is **heating** (`resolve_operation_mode(operation_state) == MODE_HEATING`).
  Heating means the outdoor coil is the evaporator, so `EVO` is the relevant valve.
- `defrost_guard.is_data_reliable` is `True` (reuses the existing guard; no sampling during
  defrost/recovery windows).
- Compressor running with frequency in a steady band `[MIN_FREQUENCY, MAX_FREQUENCY]`
  (excludes idle and startup/extreme load, keeping load roughly comparable).
- `Tg`, `Te`, `EVO`, `outdoor_temp` all present (not `None`) and plausible:
  `-10 ≤ SH ≤ 40 K`, `0 ≤ EVO ≤ 100 %` (datasheet range, confirmed
  `docs/gateway/atw-mbs-02.md`), `-60 ≤ Te ≤ 40 °C`, `-40 ≤ outdoor_temp ≤ 40 °C`. The
  plausibility clamp also guards `EVO`'s missing-deserializer `0xFFFF` (= 65535) case.
- At most one sample per `SAMPLE_MIN_INTERVAL_S` (60 s), throttled like COP.

Each sample records `(superheat = Tg − Te, evo, te, outdoor_temp)` into the day's buffer.

### Daily aggregation

At a date rollover (host local time, matching the thermal daily-energy reset), the previous
day is flushed: if it has
`≥ MIN_SAMPLES_PER_DAY` (30) samples it becomes a **valid** `DailyAggregate` holding the
**median** of superheat, evo, te and outdoor_temp for the day (medians are robust to
outliers); otherwise the day is discarded. Aggregates are stored in an
`InMemoryStorage(max_len=HISTORY_DAYS)` (45), oldest pruned first.

### Baseline and evaluation

The **baseline is frozen once**, tracked by an explicit `baseline: RefrigerantBaseline |
None` field (never re-inferred from the aggregate list, which ages out of the 45-slot
window). Let `V` be the current valid daily aggregates (chronological).

- Baseline not yet frozen and fewer than `BASELINE_DAYS` (14) valid days accumulated →
  status `learning`. When the 14th valid day arrives, freeze `baseline` = per-metric median
  over those first 14 days (superheat, evo, te, **and baseline outdoor_temp**).
- **Recent window** = the last up-to-`EVAL_DAYS` (7) valid days. Need `≥ MIN_EVAL_DAYS` (3)
  → otherwise status `ok` (baseline frozen, still accumulating).
- `dSH` = recent-median superheat − baseline superheat (all recent days; superheat is a
  *regulated* quantity, so this is seasonally robust).
- **EVO is compared like-for-like on outdoor temperature.** `dEVO` is computed only over
  recent days whose median outdoor_temp is within `±TEMP_MATCH_K` (4 K) of the baseline
  outdoor_temp. If fewer than `MIN_EVAL_DAYS` temp-matched recent days exist, `dEVO` is
  `None` (corroboration unavailable).
- `dTe` (recent − baseline) is recorded for the attributes only; it is **not** a gate,
  because `Te` moves strongly with outdoor temperature (see rationale below).

### Classification (leak signature)

`SH` (regulated → seasonally robust) is the primary signal; `EVO` corroborates only when it
can be compared at equivalent outdoor temperature. This is deliberately conservative to
avoid F-Gas-implying false alarms at the first cold spell:

| Status  | Condition |
|---------|-----------|
| `alert` | `dSH ≥ SH_ALERT (5 K)` **and** `dEVO` available **and** `dEVO ≥ EVO_ALERT (15 %)` |
| `watch` | `dSH ≥ SH_WATCH (3 K)` (SH drift alone; EVO not required) |
| `ok`    | otherwise |

Rationale for demoting `Te` and temp-matching `EVO`: at fixed target superheat and load,
`EVO` position and `Te` still vary strongly with outdoor temperature; a baseline frozen on
mild early-season days vs. a colder recent window produces benign `dEVO↑`/`dTe↓` that would
otherwise mimic a leak. Superheat does not have this bias. Thresholds are heuristic and
conservative; `Tg`/`Te` are whole-degree integers (`convert_signed_16bit`), so `SH` has ~1 K
quantization — daily medians recover sub-degree resolution, and the 3 K / 5 K thresholds sit
comfortably above the noise floor. All documented as such.

### Re-baseline / reset

After a legitimate refrigerant top-up or EXV service the frozen baseline is stale and would
alert forever. A **reset button** (`button.*_reset_refrigerant_baseline`, on the Primary
Compressor device) clears the monitor state, deletes the `Store` payload, and removes any
active repair issue. This is the only supported reset (a config reload alone must *not* wipe
the baseline, since `Store` persists it deliberately).

### Alert persistence → repair issue

At each daily flush the day's status is evaluated; an `alert_streak` counter increments on
`alert` and resets otherwise (persisted in the `Store` state). The repair issue is
raised/cleared from `coordinator._async_update_data` (the established update-driven pattern,
mirroring the `connection_error` issue), **not** from `__init__.py`: when
`alert_streak ≥ ALERT_PERSIST_DAYS` (3) raise `refrigerant_charge_alert_{entry_id}`
(`WARNING`, non-fixable, self-clearing); delete it when the status leaves `alert`. The live
sensor always reflects the current classification.

---

## 5. Public surfaces

### Domain models (`domain/models/refrigerant.py`)

- `RefrigerantInput` — dataclass: `operation_mode: str | None`, `compressor_frequency:
  float | None`, `gas_temp`, `evaporator_temp`, `outdoor_expansion_valve`, `outdoor_temp`,
  `data_reliable: bool`.
- `DailyAggregate` — NamedTuple: `day: date`, `superheat`, `evaporation_temp`, `exv`,
  `outdoor_temp`, `sample_count`.
- `RefrigerantBaseline` — dataclass: `superheat`, `evaporation_temp`, `exv`, `outdoor_temp`,
  `days`.
- `RefrigerantStatus` — dataclass: `status: str`, `superheat_delta`, `exv_delta` (`None`
  when not temp-matched), `evaporation_temp_delta`, `baseline: RefrigerantBaseline | None`,
  `valid_days`, `today_samples`, `alert_streak`.

### Domain service (`domain/services/refrigerant.py`)

- Tuning constants (module-level, imported by tests).
- `RefrigerantMonitor(storage: Storage[DailyAggregate])` with:
  `update(data, *, timestamp=None)`, `get_status() -> RefrigerantStatus`,
  `serialize() -> dict`, `restore(state: dict)`.

### Adapter (`adapters/derived_metrics.py`)

- Instantiate the monitor in `__init__` (gated on `supports_extended_compressor_sensors`;
  when unsupported the monitor is `None` and `_update_refrigerant` is a no-op), add
  `_update_refrigerant(data)` to `update()`, write:
  `data["refrigerant_charge_status"]` and `_superheat_delta` / `_exv_delta` /
  `_evaporation_temp_delta` / `_baseline_days` / `_valid_days` / `_alert_streak`.
- Expose `serialize_refrigerant()` / `restore_refrigerant(state)` passthroughs and a
  `refrigerant_status` property (the latest `RefrigerantStatus`) for the coordinator repair
  check and the reset button. Hold the `Store` and trigger `async_delay_save` on flush.

### Entity (`entities/compressor/`)

- `HitachiYutakiRefrigerantSensor(HitachiYutakiSensor)` on the **Primary Compressor**
  device (`DEVICE_PRIMARY_COMPRESSOR`): `device_class=ENUM`,
  `options=[learning, ok, watch, alert]`, `entity_category=DIAGNOSTIC`,
  `entity_registry_enabled_default=True` (headline user-facing feature; persistence lives in
  the adapter `Store`, so it does not depend on the entity being enabled). State and
  attributes come from `value_fn` / `attributes_fn` reading `coordinator.data` (no override
  needed). Built by a new `build_refrigerant_sensors(...)` gated on
  `supports_extended_compressor_sensors`, called from `sensor.py`.
- `button.py` + `entities/compressor/buttons.py`: `HitachiYutakiResetRefrigerantBaselineButton`
  (`EntityCategory.CONFIG`, gated the same way) → calls
  `coordinator.derived_metrics.reset_refrigerant()` which clears the monitor, deletes the
  `Store` payload, and removes the repair issue. `button.py` is a new platform file added to
  `PLATFORMS` in `__init__.py`.

### Repair issue + translations + docs

- Raise/clear `refrigerant_charge_alert_{entry_id}` from `coordinator._async_update_data`
  (non-fixable, self-clearing). Add `issues.refrigerant_charge_alert`, the
  `entity.sensor.refrigerant_charge_status` state map, and the
  `entity.button.reset_refrigerant_baseline` name to `translations/en.json` (+ fr; nl/ro via
  Weblate). Add a `docs/reference/` page (and link it from the index + doc-sync map) and a
  `CHANGELOG.md` `[Unreleased]` entry.

---

## 6. Testing

Pure-domain tests in `tests/domain/test_refrigerant.py`, mirroring `test_cop.py` /
`test_timing.py`: a `_make_input(...)` builder, `InMemoryStorage(max_len=...)`, injected
`timestamp`s to walk simulated days forward, and `monkeypatch` of the module `time` for the
interval throttle. Cases: sampling gate (mode/reliability/frequency/None/plausibility),
daily flush + `MIN_SAMPLES_PER_DAY`, `learning → ok` after warm-up, `watch` on SH-only
drift, `alert` on a synthetic leak drift with temp-matched EVO, **no false alert on a
cold-weather shift** (EVO/Te move but SH stable, and EVO not temp-matched), `dEVO=None` when
no temp-matched recent days, alert-streak increment/reset, serialize/restore round-trip, and
reset clearing the baseline.

---

## 7. Risks and limits (documented for users)

- Needs several weeks of heating operation before it can fire (warm-up: 14 valid baseline
  days + 3 recent). Off-season it stays `learning`.
- Heating-mode only in iteration 1; cooling-dominant installs won't accumulate data. DHW/pool
  cycles are excluded by construction (distinct operation modes).
- Heuristic thresholds → false positives possible on unusual load patterns; the SH-primary +
  temp-matched-EVO rule and daily medians mitigate this. The repair text states it is
  advisory and complements the mandatory inspection.
- After a refrigerant top-up or EXV service the baseline is stale until reset via the reset
  button; documented in the repair text and the reference page.
- Excludes Yutampo R32 (no `Tg`/`EVO`).
- `SH` has ~1 K quantization (integer-degree registers); mitigated by daily medians.
