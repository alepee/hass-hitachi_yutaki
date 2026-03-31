# Dict-Based Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rigid MetricPoint dataclass (60+ named fields, duplicated 7 times) with a dict-based telemetry model. The collector sends `coordinator.data` as-is — data keys are the vocabulary. Remove client-side daily stats aggregation in favor of the existing server-side TimescaleDB continuous aggregate.

**Architecture:** The collector becomes a thin buffer: snapshot the data dict each cycle, strip `is_available`, add timestamp, anonymize by key pattern. The MetricPoint, DailyStats, and aggregator are deleted. The Worker validator switches from field whitelist to type-based validation. The `metrics` DB table gets a JSONB column for flexible data.

**Tech Stack:** Python 3.12, pytest, TypeScript (Cloudflare Worker), PostgreSQL/TimescaleDB

**Prerequisite:** Plan 1 (DerivedMetricsAdapter) must be completed first — the collector needs enriched data in `coordinator.data`.

**Key codebase patterns:**
- Tests: `make test` (Python), `cd backend/worker && npm test` (Worker)
- Worker deploy: `cd backend/worker && npx wrangler deploy`
- Conventional commits, no Co-Authored-By

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `telemetry/collector.py` | **Rewrite** | Buffer dicts instead of MetricPoints |
| `telemetry/models.py` | Modify | Remove MetricPoint, DailyStats. Keep TelemetryLevel, InstallationInfo, MetricsBatch (now carries dicts), RegisterSnapshot |
| `telemetry/anonymizer.py` | **Rewrite** | Pattern-based anonymization on dicts instead of field-by-field dataclass replace |
| `telemetry/aggregator.py` | **Delete** | Server-side aggregation replaces client-side |
| `coordinator.py` | Modify | Remove daily accumulator, simplify flush |
| `__init__.py` | Modify | Remove daily stats flush timer logic |
| `telemetry/http_client.py` | Modify | Remove `send_daily_stats()` |
| `telemetry/noop_client.py` | Modify | Remove `send_daily_stats()` |
| `telemetry/__init__.py` | Modify | Update exports |
| `backend/worker/src/validator.ts` | Modify | Replace METRIC_FIELDS whitelist with type validation |
| `backend/worker/src/types.ts` | Modify | MetricPoint becomes `Record<string, unknown>` |
| `backend/worker/src/db.ts` | Modify | writeMetrics uses JSONB insert |
| `backend/migrations/007_jsonb_metrics.sql` | **Create** | Add JSONB `data` column or new table |
| `tests/test_telemetry_collector.py` | **Rewrite** | Test dict-based collection |
| `tests/test_telemetry_anonymizer.py` | Modify | Test pattern-based anonymization |
| `tests/test_telemetry_models.py` | Modify | Remove MetricPoint/DailyStats tests |
| `tests/test_telemetry_aggregator.py` | **Delete** | No more client-side aggregation |
| `tests/test_telemetry_integration.py` | Modify | Remove daily stats tests, update flush tests |

---

### Task 1: Rewrite collector to buffer dicts

Replace the MetricPoint-constructing collector with a thin dict buffer.

**Files:**
- Rewrite: `custom_components/hitachi_yutaki/telemetry/collector.py`
- Rewrite: `tests/test_telemetry_collector.py`

- [ ] **Step 1: Write new collector tests**

Replace `tests/test_telemetry_collector.py`:

```python
"""Tests for telemetry collector (dict-based)."""

from datetime import UTC

from custom_components.hitachi_yutaki.telemetry.collector import TelemetryCollector
from custom_components.hitachi_yutaki.telemetry.models import TelemetryLevel


def _sample_data(**overrides) -> dict:
    """Create a sample coordinator data dict."""
    data = {
        "is_available": True,
        "outdoor_temp": 5.5,
        "water_inlet_temp": 35.0,
        "water_outlet_temp": 40.5,
        "dhw_current_temp": 52.0,
        "compressor_frequency": 65.0,
        "compressor_current": 8.5,
        "unit_mode": 1,
        "operation_state": "operation_state_heat_thermo_on",
        "thermal_power_heating": 5.2,
        "cop_heating": 1.32,
    }
    data.update(overrides)
    return data


class TestCollectorLevel:
    """Tests for level-based collection behavior."""

    def test_off_does_not_collect(self):
        """OFF level ignores all data."""
        collector = TelemetryCollector(TelemetryLevel.OFF)
        collector.collect(_sample_data())
        assert collector.buffer_size == 0

    def test_on_collects(self):
        """ON level collects data."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        assert collector.buffer_size == 1


class TestDictCollection:
    """Tests for dict-based data collection."""

    def test_snapshot_preserves_data_keys(self):
        """Collected dict preserves all data keys from coordinator."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        point = collector.flush()[0]
        assert point["outdoor_temp"] == 5.5
        assert point["water_inlet_temp"] == 35.0
        assert point["cop_heating"] == 1.32

    def test_is_available_excluded(self):
        """The internal 'is_available' key is stripped."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        point = collector.flush()[0]
        assert "is_available" not in point

    def test_timestamp_added(self):
        """Each collected dict gets a UTC timestamp."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        point = collector.flush()[0]
        assert "time" in point
        assert point["time"].tzinfo == UTC

    def test_original_data_not_mutated(self):
        """collect() does not mutate the original data dict."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        data = _sample_data()
        original_keys = set(data.keys())
        collector.collect(data)
        assert set(data.keys()) == original_keys
        assert "time" not in data

    def test_skips_unavailable_data(self):
        """Data marked unavailable is not collected."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect({"is_available": False, "outdoor_temp": 10})
        assert collector.buffer_size == 0

    def test_skips_empty_data(self):
        """Empty data dict is not collected."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect({})
        assert collector.buffer_size == 0


class TestCollectorBuffer:
    """Tests for buffer behavior."""

    def test_flush_returns_and_clears(self):
        """flush() returns all buffered dicts and empties the buffer."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        collector.collect(_sample_data())
        assert collector.buffer_size == 2
        points = collector.flush()
        assert len(points) == 2
        assert collector.buffer_size == 0

    def test_flush_empty_returns_empty_list(self):
        """Flushing empty buffer returns empty list."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        assert collector.flush() == []

    def test_buffer_overflow_drops_oldest(self):
        """Oldest dicts are dropped when buffer exceeds max size."""
        collector = TelemetryCollector(TelemetryLevel.ON, buffer_max_size=3)
        for i in range(5):
            collector.collect(_sample_data(outdoor_temp=float(i)))
        assert collector.buffer_size == 3
        points = collector.flush()
        assert points[0]["outdoor_temp"] == 2.0
        assert points[2]["outdoor_temp"] == 4.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — collector still returns MetricPoint objects

- [ ] **Step 3: Rewrite collector**

Replace `custom_components/hitachi_yutaki/telemetry/collector.py`:

```python
"""Telemetry collector — buffers coordinator data dicts for periodic send."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
import logging
from typing import Any

from .models import TelemetryLevel

_LOGGER = logging.getLogger(__name__)

# Default buffer size: 360 points = 30 minutes at 5s poll interval
DEFAULT_BUFFER_MAX_SIZE = 360

# Keys to exclude from telemetry (internal coordinator flags)
_EXCLUDED_KEYS = frozenset({"is_available"})


class TelemetryCollector:
    """Buffers coordinator data dicts for periodic telemetry send.

    Each call to collect() snapshots the data dict (minus excluded keys)
    and adds a UTC timestamp. The buffer is a circular deque — when full,
    oldest entries are dropped.
    """

    def __init__(
        self,
        level: TelemetryLevel,
        buffer_max_size: int = DEFAULT_BUFFER_MAX_SIZE,
    ) -> None:
        """Initialize the collector."""
        self._level = level
        self._buffer: deque[dict[str, Any]] = deque(maxlen=buffer_max_size)

    @property
    def level(self) -> TelemetryLevel:
        """Return the current telemetry level."""
        return self._level

    @property
    def buffer_size(self) -> int:
        """Return the current number of buffered points."""
        return len(self._buffer)

    def collect(self, data: dict[str, Any]) -> None:
        """Snapshot the data dict and add to the buffer.

        Skips collection when level is OFF or data is unavailable.
        """
        if self._level == TelemetryLevel.OFF:
            return

        if not data or not data.get("is_available"):
            return

        # Shallow copy, exclude internal keys, add timestamp
        point = {
            k: v for k, v in data.items() if k not in _EXCLUDED_KEYS
        }
        point["time"] = datetime.now(tz=UTC)

        self._buffer.append(point)

    def flush(self) -> list[dict[str, Any]]:
        """Return all buffered dicts and clear the buffer."""
        points = list(self._buffer)
        self._buffer.clear()
        return points
```

- [ ] **Step 4: Run tests**

Run: `make test`
Expected: New collector tests PASS. Some existing tests will FAIL (telemetry integration tests that expect MetricPoint).

- [ ] **Step 5: Commit**

```bash
git add custom_components/hitachi_yutaki/telemetry/collector.py tests/test_telemetry_collector.py
git commit -m "refactor(telemetry): rewrite collector to buffer dicts instead of MetricPoints"
```

---

### Task 2: Rewrite anonymizer for dict-based data

Replace field-by-field dataclass anonymization with pattern-based dict anonymization.

**Files:**
- Rewrite: `custom_components/hitachi_yutaki/telemetry/anonymizer.py`
- Modify: `tests/test_telemetry_anonymizer.py`

- [ ] **Step 1: Write anonymizer tests**

```python
"""Tests for dict-based telemetry anonymizer."""

from custom_components.hitachi_yutaki.telemetry.anonymizer import (
    anonymize_point,
    hash_instance_id,
    round_coordinate,
    round_temperature,
)


class TestRoundTemperature:
    """Existing tests — keep as-is."""

    def test_rounds_to_half_degree(self):
        assert round_temperature(5.3) == 5.5
        assert round_temperature(5.7) == 5.5
        assert round_temperature(5.0) == 5.0

    def test_none_returns_none(self):
        assert round_temperature(None) is None


class TestAnonymizePoint:
    """Tests for dict-based point anonymization."""

    def test_temperature_keys_rounded(self):
        """All keys containing '_temp' are rounded to 0.5°C."""
        point = {
            "outdoor_temp": 5.3,
            "water_inlet_temp": 34.8,
            "dhw_current_temp": 51.7,
            "compressor_frequency": 65.0,
        }
        result = anonymize_point(point)
        assert result["outdoor_temp"] == 5.5
        assert result["water_inlet_temp"] == 35.0
        assert result["dhw_current_temp"] == 51.5
        # Non-temp fields unchanged
        assert result["compressor_frequency"] == 65.0

    def test_cop_keys_rounded_to_one_decimal(self):
        """COP values are rounded to 1 decimal place."""
        point = {"cop_heating": 1.3456, "cop_cooling": 2.789}
        result = anonymize_point(point)
        assert result["cop_heating"] == 1.3
        assert result["cop_cooling"] == 2.8

    def test_water_flow_rounded(self):
        """Water flow is rounded to 1 decimal."""
        point = {"water_flow": 12.345}
        result = anonymize_point(point)
        assert result["water_flow"] == 12.3

    def test_none_values_preserved(self):
        """None values pass through unchanged."""
        point = {"outdoor_temp": None, "cop_heating": None}
        result = anonymize_point(point)
        assert result["outdoor_temp"] is None
        assert result["cop_heating"] is None

    def test_non_numeric_values_unchanged(self):
        """String and boolean values pass through."""
        point = {"operation_state": "heat", "unit_power": True}
        result = anonymize_point(point)
        assert result["operation_state"] == "heat"
        assert result["unit_power"] is True

    def test_does_not_mutate_original(self):
        """anonymize_point returns a new dict."""
        point = {"outdoor_temp": 5.3}
        result = anonymize_point(point)
        assert result is not point
        assert point["outdoor_temp"] == 5.3
```

- [ ] **Step 2: Rewrite anonymizer**

```python
"""Anonymization utilities for telemetry data."""

from __future__ import annotations

import hashlib
from typing import Any

from .models import InstallationInfo


def hash_instance_id(instance_id: str) -> str:
    """Hash an HA instance ID with SHA-256 (non-reversible)."""
    return hashlib.sha256(instance_id.encode()).hexdigest()


def round_temperature(value: float | None, precision: float = 0.5) -> float | None:
    """Round a temperature to the nearest increment (default 0.5°C)."""
    if value is None:
        return None
    return round(value / precision) * precision


def round_coordinate(value: float | None, precision: float = 1.0) -> float | None:
    """Round a geographic coordinate to the nearest degree (default 1°)."""
    if value is None:
        return None
    return round(value / precision) * precision


def anonymize_installation_info(info: InstallationInfo) -> InstallationInfo:
    """Anonymize InstallationInfo by rounding geographic coordinates."""
    from dataclasses import replace
    return replace(
        info,
        latitude=round_coordinate(info.latitude),
        longitude=round_coordinate(info.longitude),
    )


def anonymize_point(point: dict[str, Any]) -> dict[str, Any]:
    """Anonymize a telemetry data point by rounding sensitive values.

    Rules (applied by key pattern):
    - Keys containing '_temp': round to 0.5°C
    - Keys starting with 'cop_' (excluding quality/measurements): round to 1 decimal
    - 'water_flow': round to 1 decimal

    Returns a new dict (does not mutate the original).
    """
    result = {}
    for key, value in point.items():
        if value is None or not isinstance(value, (int, float)):
            result[key] = value
            continue

        if "_temp" in key:
            result[key] = round_temperature(value)
        elif key.startswith("cop_") and key not in (
            "cop_heating_quality",
            "cop_cooling_quality",
            "cop_dhw_quality",
            "cop_pool_quality",
            "cop_heating_measurements",
            "cop_cooling_measurements",
            "cop_dhw_measurements",
            "cop_pool_measurements",
            "cop_heating_time_span_minutes",
            "cop_cooling_time_span_minutes",
            "cop_dhw_time_span_minutes",
            "cop_pool_time_span_minutes",
        ):
            result[key] = round(value, 1)
        elif key == "water_flow":
            result[key] = round(value, 1)
        else:
            result[key] = value

    return result
```

- [ ] **Step 3: Run tests**

Run: `make test`
Expected: Anonymizer tests PASS

- [ ] **Step 4: Commit**

```bash
git add custom_components/hitachi_yutaki/telemetry/anonymizer.py tests/test_telemetry_anonymizer.py
git commit -m "refactor(telemetry): pattern-based dict anonymization replaces field-by-field"
```

---

### Task 3: Update models — remove MetricPoint and DailyStats

Clean up the models to reflect the dict-based approach.

**Files:**
- Modify: `custom_components/hitachi_yutaki/telemetry/models.py`
- Modify: `custom_components/hitachi_yutaki/telemetry/__init__.py`
- Delete: `custom_components/hitachi_yutaki/telemetry/aggregator.py`
- Delete: `tests/test_telemetry_aggregator.py`
- Modify: `tests/test_telemetry_models.py`

- [ ] **Step 1: Update models.py**

Remove `MetricPoint` and `DailyStats` dataclasses. Update `MetricsBatch` to carry `list[dict]`:

```python
@dataclass(frozen=True)
class MetricsBatch:
    """A batch of metric data points for a single instance."""

    instance_hash: str
    points: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON payload."""
        return {
            "type": "metrics",
            "instance_hash": self.instance_hash,
            "points": self.points,
        }
```

Keep `TelemetryLevel`, `InstallationInfo`, `RegisterSnapshot` unchanged.

- [ ] **Step 2: Delete aggregator**

Delete `custom_components/hitachi_yutaki/telemetry/aggregator.py` and `tests/test_telemetry_aggregator.py`.

- [ ] **Step 3: Update __init__.py exports**

Remove `MetricPoint`, `DailyStats` from exports. Remove aggregator import.

- [ ] **Step 4: Update model tests**

In `tests/test_telemetry_models.py`, remove MetricPoint and DailyStats test classes. Update MetricsBatch tests to use dicts.

- [ ] **Step 5: Run tests**

Run: `make test`
Expected: Model tests PASS. Some integration tests may still fail.

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "refactor(telemetry): remove MetricPoint and DailyStats models

MetricsBatch now carries list[dict]. DailyStats aggregation moved
server-side (TimescaleDB continuous aggregate). Aggregator deleted."
```

---

### Task 4: Simplify coordinator flush and remove daily accumulator

The coordinator flush sends dicts directly. No more daily stats accumulation.

**Files:**
- Modify: `custom_components/hitachi_yutaki/coordinator.py`
- Modify: `custom_components/hitachi_yutaki/__init__.py`
- Modify: `custom_components/hitachi_yutaki/telemetry/http_client.py`
- Modify: `custom_components/hitachi_yutaki/telemetry/noop_client.py`
- Modify: `tests/test_telemetry_integration.py`

- [ ] **Step 1: Simplify coordinator flush**

In `coordinator.py`, replace `async_flush_telemetry()`:

```python
async def async_flush_telemetry(self) -> None:
    """Flush telemetry buffer and send data."""
    points = self.telemetry_collector.flush()
    if not points:
        return

    instance_hash = self._telemetry_meta["instance_hash"]

    try:
        # Anonymize each point
        anonymized = [anonymize_point(p) for p in points]
        batch = MetricsBatch(instance_hash=instance_hash, points=anonymized)
        success = await self.telemetry_client.send_metrics(batch)

        if success:
            self.telemetry_last_send = datetime.now(tz=UTC)
        else:
            self.telemetry_send_failures += 1
    except Exception:
        self.telemetry_send_failures += 1
        _LOGGER.warning("Telemetry flush failed", exc_info=True)
```

Remove from coordinator:
- `_daily_points_accumulator` and `_daily_stats_date` from `__init__`
- All daily stats logic from flush
- `aggregate_metrics` and `anonymize_daily_stats` imports

- [ ] **Step 2: Remove send_daily_stats from clients**

In `telemetry/http_client.py`, remove `send_daily_stats()` method.
In `telemetry/noop_client.py`, remove `send_daily_stats()` method.

- [ ] **Step 3: Simplify collector.collect() call**

In `coordinator._async_update_data()`, simplify the collect call:

```python
# Before:
self.telemetry_collector.collect(
    data,
    is_compressor_running=self.api_client.is_compressor_running,
    is_defrosting=self.api_client.is_defrosting,
)

# After (collector just takes the dict):
self.telemetry_collector.collect(data)
```

Note: `is_compressor_running` and `is_defrosting` should already be in `coordinator.data` as data keys (injected by the DerivedMetricsAdapter or directly from the API client). The implementer should verify these keys exist in data and add them if not.

- [ ] **Step 4: Update __init__.py**

Remove daily-stats-specific flush interval logic if any remains. The flush timer stays (5 min for metrics).

- [ ] **Step 5: Update integration tests**

In `tests/test_telemetry_integration.py`:
- Remove `TestFullModeDailyStats` class
- Update `test_flush_full_sends_metrics_batch` to expect dict-based MetricsBatch
- Remove `send_daily_stats` assertions
- Update anonymization tests to use dict patterns

- [ ] **Step 6: Run all tests**

Run: `make test && make check`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "refactor(telemetry): simplify flush — dict-based, no client-side daily stats

Coordinator flush sends anonymized dicts directly. Daily stats
aggregation removed — TimescaleDB continuous aggregate (metrics_daily_agg)
is the authoritative source. Daily accumulator deleted."
```

---

### Task 5: Update backend Worker for dict-based metrics

The Worker validator needs to accept dynamic dict keys instead of a fixed whitelist.

**Files:**
- Modify: `backend/worker/src/validator.ts`
- Modify: `backend/worker/src/types.ts`
- Modify: `backend/worker/src/db.ts`
- Create: `backend/migrations/007_jsonb_metrics.sql`

- [ ] **Step 1: Update TypeScript types**

In `types.ts`, replace `MetricPoint` interface with a flexible type:

```typescript
/** Single metric data point — dynamic keys from integration data keys. */
export interface MetricPoint {
  time: string;
  [key: string]: unknown;
}
```

- [ ] **Step 2: Update validator**

In `validator.ts`, replace the `METRIC_FIELDS` whitelist with type-based validation:

```typescript
function validateMetrics(
  payload: Record<string, unknown>,
  instanceHash: string,
): MetricsPayload {
  const points = payload.points;
  if (!Array.isArray(points) || points.length === 0) {
    throw new ValidationError("metrics: points must be a non-empty array");
  }
  if (points.length > MAX_METRICS_POINTS) {
    throw new ValidationError(`metrics: too many points (max ${MAX_METRICS_POINTS})`);
  }

  const sanitized: MetricPoint[] = points.map((p: unknown, i: number) => {
    if (typeof p !== "object" || p === null) {
      throw new ValidationError(`metrics: point[${i}] must be an object`);
    }
    const point = p as Record<string, unknown>;
    if (typeof point.time !== "string") {
      throw new ValidationError(`metrics: point[${i}].time is required`);
    }

    // Type validation: only allow primitive values (no nested objects)
    const clean: MetricPoint = { time: point.time as string };
    for (const [key, value] of Object.entries(point)) {
      if (key === "time") continue;
      if (
        typeof value === "number" ||
        typeof value === "boolean" ||
        typeof value === "string" ||
        value === null
      ) {
        clean[key] = value;
      }
      // Silently drop non-primitive values (arrays, objects)
    }
    return clean;
  });

  return {
    type: "metrics",
    instance_hash: instanceHash,
    points: sanitized,
  };
}
```

Remove the `METRIC_FIELDS` set (no longer needed).

- [ ] **Step 3: Update DB write to use JSONB**

Create `backend/migrations/007_jsonb_metrics.sql`:

```sql
-- 007_jsonb_metrics.sql
-- Add JSONB data column for flexible metric storage.
-- Existing typed columns remain for backward compatibility with current dashboards.

ALTER TABLE metrics ADD COLUMN data JSONB;
```

In `db.ts`, update `writeMetrics()` to store the full dict in the JSONB column while still populating typed columns for backward compatibility:

```typescript
export async function writeMetrics(
  client: Client,
  payload: MetricsPayload,
): Promise<void> {
  const values: unknown[] = [];
  const placeholders: string[] = [];

  for (let i = 0; i < payload.points.length; i++) {
    const p = payload.points[i];
    const offset = i * 3;
    placeholders.push(`($${offset + 1}, $${offset + 2}, $${offset + 3})`);
    values.push(
      p.time,
      payload.instance_hash,
      JSON.stringify(p),
    );
  }

  await client.query(
    `INSERT INTO metrics (time, instance_hash, data) VALUES ${placeholders.join(",")}`,
    values,
  );
}
```

Note: This is a simplified approach. The existing typed columns (`outdoor_temp`, etc.) are kept for backward dashboard compatibility. A future migration can extract values from JSONB into typed columns if needed, or dashboards can query JSONB directly.

- [ ] **Step 4: Run Worker tests**

Run: `cd backend/worker && npm test`
Expected: PASS (if tests exist), or verify manually

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat(backend): accept dict-based metrics with JSONB storage

Worker validator uses type-based validation instead of field whitelist.
Metrics stored in JSONB column for flexible schema. Existing typed
columns kept for backward compatibility."
```

---

### Task 6: Update Grafana dashboards for JSONB queries

Update dashboards to query from the JSONB `data` column.

**Files:**
- Modify: `backend/grafana/performance.json`
- Modify: `backend/grafana/fleet-overview.json`

- [ ] **Step 1: Update Performance dashboard queries**

For each panel, update the SQL to read from JSONB:

```sql
-- Before:
SELECT time, outdoor_temp AS "Outdoor °C" FROM metrics WHERE outdoor_temp IS NOT NULL ...

-- After:
SELECT time, (data->>'outdoor_temp')::real AS "Outdoor °C" FROM metrics WHERE data->>'outdoor_temp' IS NOT NULL ...
```

Or, if both old and new data coexist:

```sql
SELECT time, COALESCE(outdoor_temp, (data->>'outdoor_temp')::real) AS "Outdoor °C"
FROM metrics
WHERE outdoor_temp IS NOT NULL OR data->>'outdoor_temp' IS NOT NULL ...
```

- [ ] **Step 2: Update Fleet Overview metrics count**

The `Metrics Points (24h)` counter should count both old and new format rows.

- [ ] **Step 3: Commit**

```bash
git add backend/grafana/
git commit -m "feat(grafana): update dashboards to query JSONB metrics data"
```

---

### Task 7: Final cleanup and verification

- [ ] **Step 1: Run full Python test suite**

Run: `make test && make check`
Expected: All PASS, no lint errors

- [ ] **Step 2: Verify telemetry data flow end-to-end**

Check that:
- Collector buffers dicts with all data keys
- Anonymizer rounds temperatures and COP by pattern
- HTTP client sends valid JSON payload
- No references to MetricPoint remain (grep for it)

```bash
grep -r "MetricPoint" custom_components/hitachi_yutaki/ tests/ --include="*.py"
```

Expected: No matches (except possibly in comments or type hints being cleaned up).

- [ ] **Step 3: Verify no references to DailyStats or aggregator remain**

```bash
grep -r "DailyStats\|daily_stats\|aggregate_metrics\|aggregator" custom_components/hitachi_yutaki/ tests/ --include="*.py"
```

Expected: No matches (except possibly coordinator attribute cleanup).

- [ ] **Step 4: Commit any fixups**

```bash
git add -u
git commit -m "chore(telemetry): final cleanup — remove dead references"
```
