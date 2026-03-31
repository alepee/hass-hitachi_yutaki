# Telemetry Architecture Refactor — DerivedMetricsAdapter & Dict-Based Collection

**Date:** 2026-03-31

## Context

The telemetry system has several architectural issues identified during a comprehensive review:

1. **COP mismatch:** The telemetry collector computes COP using only the primary Modbus compressor current, while HA entities use external power sensors and secondary compressor data. For a S80 cascade, telemetry COP averages 8.2 vs 1.32 in HA — wrong by 6x.

2. **Entity complexity:** COP and thermal sensors instantiate their own domain services (~340 lines each), manage state, rehydrate from Recorder. They should be simple readers like all other sensors.

3. **Field duplication:** The MetricPoint dataclass defines 60+ named fields that are duplicated across 7 files (Python models, serializer, collector, anonymizer, TypeScript types, validator, DB writer). Adding a field requires changing all 7.

4. **Coordinator overload:** The coordinator manages Modbus polling, defrost guard, telemetry collection, flush, daily accumulation, snapshot sending, retry logic — too many responsibilities.

5. **Daily stats never arrive:** The in-memory daily accumulator is lost on HA restart. After 2 days of live data from 5 installations, the daily_stats table has 0 rows.

These issues share a root cause: the data computation and telemetry collection are wired in the wrong place.

## Design

### 1. Data Keys — Rename from Register Keys

Register keys are the stable business vocabulary of the integration: `"outdoor_temp"`, `"compressor_frequency"`, `"cop_heating"`. They abstract the gateway transport (Modbus, Wi-Fi, API) and are used everywhere from the register map to coordinator.data to entity descriptions.

The term "register key" is an artifact of the Modbus-only era. With derived metrics (COP, thermal_power) and future non-Modbus gateways, these identifiers are gateway-agnostic.

**Decision:** Rename "register key" to **"data key"** throughout the project. This is a terminology change — the mechanism stays the same. The rename is cosmetic and can be done incrementally (no breaking change).

### 2. DerivedMetricsAdapter — Compute Before Entities

A new adapter in `adapters/derived_metrics.py` that orchestrates the existing domain services and injects computed values into `coordinator.data` before entities read it.

**Responsibilities:**
- Instantiate stateful domain services (COPService × 4 modes, ThermalPowerService, ElectricalPowerCalculatorAdapter)
- Call services on each poll cycle via `update(data)` — mutates the dict in-place
- Handle Recorder rehydration at startup via `async_rehydrate()`
- Maintain state between cycles (EnergyAccumulator history, quality levels)

**What it computes (injected data keys):**
- `thermal_power_heating`, `thermal_power_cooling` — from water temps + flow
- `electrical_power` — from compressor current (or external power entity)
- `cop_heating`, `cop_cooling`, `cop_dhw`, `cop_pool` — from thermal/electrical ratio over time
- `cop_heating_quality`, etc. — quality assessment (no_data → optimal)
- `thermal_energy_heating_daily`, `thermal_energy_heating_total`, etc. — accumulated energy

**Integration in coordinator:**

```python
async def _async_update_data(self):
    data = await self._fetch_modbus_data()
    self._derived_metrics.update(data)       # enriches data in-place
    self.telemetry_collector.collect(data)    # sees enriched data
    return data                              # entities see enriched data
```

**What entities become:**

```python
# Before (COP sensor): ~340 lines, instantiates COPService, rehydrates, computes
class HitachiYutakiCOPSensor(HitachiYutakiSensor):
    def __init__(self, ...):
        self._cop_service = COPService(...)
    async def async_added_to_hass(self):
        await self._async_rehydrate_cop_history()
    @property
    def native_value(self):
        self._cop_service.update(self._get_cop_input())
        return self._cop_service.get_value()

# After: simple reader, like temperature sensors
HitachiYutakiSensorEntityDescription(
    key="cop_heating",
    value_fn=lambda c: c.data.get("cop_heating"),
)
```

The `HitachiYutakiCOPSensor` and `HitachiYutakiThermalSensor` subclasses are eliminated. All sensors use the base `HitachiYutakiSensor` class with `value_fn`.

**File structure:**

```
adapters/
  derived_metrics.py          # DerivedMetricsAdapter class
  calculators/
    thermal.py                # existing, unchanged
    electrical.py             # existing, unchanged
domain/
  services/
    cop.py                    # existing, unchanged
    thermal/                  # existing, unchanged
    electrical.py             # existing, unchanged
entities/
  base/sensor/
    cop.py                    # DELETED — no longer needed
    thermal.py                # DELETED — no longer needed
    base.py                   # simplified, no sensor_class dispatch
```

### 3. Dict-Based Telemetry Collection

The MetricPoint dataclass with 60+ named fields is replaced by a plain dict. The collector sends `coordinator.data` as-is — the data keys are the telemetry vocabulary.

**What changes:**
- `TelemetryCollector.collect(data)` buffers the raw dict (shallow copy with timestamp added)
- No field mapping, no MetricPoint construction
- The anonymizer operates on dict keys by convention (rounds all `*_temp` keys, etc.)
- The HTTP client sends the dict as JSON

**What is sent:**
- All data keys from coordinator.data (raw Modbus values + derived metrics)
- No filtering client-side — if noise reduction is needed, it's done server-side or in the database
- The `is_available` meta key is excluded (internal coordinator flag)

**Impact on backend:**
- The Worker validator switches from field whitelist to basic type validation (keys are strings, values are numbers/strings/booleans)
- The DB schema for the `metrics` table may need to accommodate dynamic columns (JSONB column, or keep current typed columns with a JSONB overflow column)
- The R2 archive already stores JSON — no change needed

### 4. Telemetry Simplification

With the collector receiving a complete dict, several components simplify:

**Collector (`telemetry/collector.py`):**
- No more field-by-field MetricPoint construction
- No more `_to_float()` sentinel filtering (sentinels already filtered by register map deserializers or DerivedMetricsAdapter)
- No more thermal/electrical/COP computation
- Becomes: buffer dicts, flush, done

**Anonymizer (`telemetry/anonymizer.py`):**
- Operates on dict keys by pattern: round values for keys matching `*_temp*` to 0.5°C, round `cop_*` to 1 decimal, etc.
- No more field-by-field `replace()` on a frozen dataclass

**Models (`telemetry/models.py`):**
- `MetricPoint` removed
- `MetricsBatch` carries `list[dict]` instead of `list[MetricPoint]`
- `DailyStats` may remain as a typed structure (it's a fixed schema) or become a dict too
- `InstallationInfo` and `RegisterSnapshot` unchanged

### 5. Daily Stats — Server-Side Aggregation

The client-side daily accumulator (`_daily_points_accumulator`) is fragile — it's lost on HA restart. TimescaleDB already has a `metrics_daily_agg` continuous aggregate that computes daily stats from the metrics hypertable automatically.

**Decision:** Remove client-side daily aggregation. The continuous aggregate is the authoritative source for daily stats. The `daily_stats` table can be populated by a scheduled job from the continuous aggregate, or dashboards can query `metrics_daily_agg` directly.

This eliminates:
- `_daily_points_accumulator` and `_daily_stats_date` from coordinator
- `aggregate_metrics()` function
- `anonymize_daily_stats()` function
- `send_daily_stats()` client method
- The `DailyStats` model
- The daily stats validation and write path in the Worker

The `daily_stats` table and Worker endpoint remain for backward compatibility but are no longer actively used by the integration.

### 6. Architecture Summary

```
┌─ Gateway ────────────────────────────────────────────┐
│  Data Key Map: register/source → "outdoor_temp"       │
│  Returns dict of data keys                            │
└──────────────────────────┬───────────────────────────-┘
                           │ raw data
                           ▼
┌─ DerivedMetricsAdapter ─────────────────────────────-┐
│  Calls domain services:                               │
│    ThermalPowerService → data["thermal_power"] = 5.2  │
│    ElectricalPower     → data["electrical_power"]=1.8 │
│    COPService(s)       → data["cop_heating"] = 1.32   │
│  Stateful (accumulators, rehydration)                 │
│  Lives in adapters/                                   │
└──────────────────────────┬───────────────────────────-┘
                           │ enriched data
                           ▼
┌─ Coordinator._async_update_data() ──────────────────-┐
│  1. fetch raw data                                    │
│  2. self._derived_metrics.update(data)                │
│  3. self.telemetry_collector.collect(data)             │
│  4. return data                                       │
└──────────────────────────┬───────────────────────────-┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
┌─ Entities ──────────┐  ┌─ Telemetry ──────────────┐
│ Simple readers       │  │ Buffers dict as-is        │
│ value_fn = c.data[k] │  │ Anonymizes by key pattern │
│ No business logic    │  │ Sends via HTTP client     │
└──────────────────────┘  └─────────────────────────-┘
```

### 7. Migration & Backward Compatibility

**Backend:** The Worker needs to accept the new dict-based payload format alongside the current MetricPoint format during transition. The simplest approach is a new payload version field.

**Existing data:** The 139K metric points already in TigerData use the current column-based schema. No migration needed — new data can coexist (JSONB column) or use the same columns (the data keys map to the same names).

**Entity unique_ids:** Unchanged — entities keep their current unique_ids. No user-facing migration.

**Config flow:** Unchanged — telemetry consent (Off/On) stays the same.

### 8. Scope & Non-Goals

**In scope:**
- DerivedMetricsAdapter implementation
- Simplify COP and thermal entities to simple readers
- Dict-based telemetry collection
- Remove client-side daily stats aggregation
- Rename "register key" to "data key" (incremental, cosmetic)

**Not in scope:**
- Backend schema migration (can be done separately)
- Worker auth (separate concern)
- R2 → Parquet conversion (separate concern)
- New gateway types (future work, but the architecture supports it)
- World model training (future work, but the data pipeline is ready)
