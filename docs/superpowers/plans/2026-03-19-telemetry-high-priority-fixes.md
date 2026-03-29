# Telemetry High-Priority Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 4 high-priority bugs preventing telemetry data from being useful: sentinel values polluting data, wrong mapping of power_consumption to electrical_power, FULL mode missing daily stats, and snapshots never sent.

**Architecture:** All fixes stay within the existing telemetry package and coordinator. Sentinel filtering goes in the collector (`_to_float`). The power_consumption→electrical_power mapping is removed (it maps cumulative energy kWh to instantaneous power, which is semantically wrong). thermal_power and COP are left NULL in telemetry — they can be recomputed server-side from raw data (water temps, flow, compressor current/frequency) which is already collected. FULL mode daily stats use a day-level accumulator to avoid sending misleading 5-minute partial aggregates.

**Tech Stack:** Python 3.12, pytest, pytest-asyncio, Home Assistant custom component patterns

**Key patterns in this codebase:**
- Test helpers: `_sample_data(**overrides)` for coordinator data dicts, `_make_coordinator(...)` factory (not fixtures)
- Coordinator stores telemetry state: `telemetry_collector`, `telemetry_client`, `_telemetry_meta`
- Domain layer is HA-agnostic — no `homeassistant.*` imports allowed

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `custom_components/hitachi_yutaki/telemetry/collector.py` | Modify | Sentinel filtering in `_to_float`, remove power_consumption mapping |
| `custom_components/hitachi_yutaki/coordinator.py` | Modify | Daily stats accumulator for FULL, wire snapshot sending |
| `tests/test_telemetry_collector.py` | Modify | Sentinel tests, update `test_extracts_power` |
| `tests/test_telemetry_integration.py` | Modify | FULL daily stats + snapshot tests |

---

### Task 1: Filter Modbus sentinel values in collector

The collector passes raw Modbus values like -127 (no sensor) and -67 (DHW not configured) straight through. These poison aggregations and dashboards.

Known sentinels from live DB data:
- `-127` → water_outlet_2_temp, water_outlet_3_temp, pool_current_temp
- `-67` → dhw_temp (when DHW tank not connected)

The entity layer already filters `-127` (see `entities/hydraulic/sensors.py:62`).

**Files:**
- Modify: `custom_components/hitachi_yutaki/telemetry/collector.py`
- Modify: `tests/test_telemetry_collector.py`

- [ ] **Step 1: Write failing tests for sentinel filtering**

Add to `tests/test_telemetry_collector.py` in a new class after `TestCollectorBuffer`:

```python
class TestSentinelFiltering:
    """Tests for Modbus sentinel value filtering."""

    def test_filters_sentinel_minus_127(self):
        """Sentinel -127 (no sensor connected) should become None."""
        collector = TelemetryCollector(TelemetryLevel.FULL)
        collector.collect(
            _sample_data(
                water_outlet_2_temp=-127,
                water_outlet_3_temp=-127,
                pool_current_temp=-127,
            ),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.water_outlet_2_temp is None
        assert point.water_outlet_3_temp is None
        assert point.pool_current_temp is None

    def test_filters_sentinel_minus_67(self):
        """Sentinel -67 (DHW not configured) should become None."""
        collector = TelemetryCollector(TelemetryLevel.FULL)
        collector.collect(
            _sample_data(dhw_current_temp=-67),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.dhw_temp is None

    def test_passes_valid_negative_temps(self):
        """Legitimate negative temperatures (e.g. -10°C outdoor) must pass through."""
        collector = TelemetryCollector(TelemetryLevel.FULL)
        collector.collect(
            _sample_data(outdoor_temp=-10, water_inlet_temp=5),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.outdoor_temp == -10
        assert point.water_inlet_temp == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — sentinels pass through as-is

- [ ] **Step 3: Implement sentinel filtering in `_to_float`**

In `collector.py`, replace `_to_float`:

```python
# Modbus sentinel values indicating "no sensor" or "not configured"
_SENTINEL_VALUES = frozenset({-127, -67})


def _to_float(value: Any) -> float | None:
    """Safely convert a value to float, returning None on failure or sentinel."""
    if value is None:
        return None
    try:
        result = float(value)
        if result in _SENTINEL_VALUES:
            return None
        return result
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/hitachi_yutaki/telemetry/collector.py tests/test_telemetry_collector.py
git commit -m "fix(telemetry): filter Modbus sentinel values (-127, -67) in collector"
```

---

### Task 2: Fix wrong power_consumption → electrical_power mapping

The collector maps `data.get("power_consumption")` to `MetricPoint.electrical_power`. But register 1098 (`power_consumption`) is **cumulative energy in kWh** (a total_increasing counter), not instantaneous power in kW. This produces misleading data (always 0 or a tiny cumulative value interpreted as power).

`thermal_power` and `cop_instant` are computed by per-entity domain services (COPService, ThermalPowerService) that maintain internal state and are not accessible from the coordinator. The raw data needed to recompute them server-side (water_inlet_temp, water_outlet_temp, water_flow, compressor_current, compressor_frequency) is already collected. So the cleanest fix is to stop sending wrong data and leave these fields NULL.

**Files:**
- Modify: `custom_components/hitachi_yutaki/telemetry/collector.py`
- Modify: `tests/test_telemetry_collector.py`

- [ ] **Step 1: Update existing `test_extracts_power` test**

The existing test at line 73 asserts `point.electrical_power == 3.2`. After removing the wrong mapping, this field should be None. Update the test:

```python
def test_power_fields_are_none_without_computed_values(self):
    """Power and COP fields are None — they require domain service computation."""
    collector = TelemetryCollector(TelemetryLevel.FULL)
    collector.collect(_sample_data(), is_compressor_running=True, is_defrosting=False)
    point = collector.flush()[0]
    # power_consumption register is cumulative kWh, not instantaneous power
    # thermal_power and cop are computed by per-entity domain services
    # All three are None in telemetry — can be recomputed server-side
    assert point.electrical_power is None
    assert point.thermal_power is None
    assert point.cop_instant is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `make test`
Expected: FAIL — `electrical_power` still returns 3.2

- [ ] **Step 3: Remove wrong mappings in collector**

In `collector.py`, in the `collect()` method, replace these three lines:

```python
# Before:
thermal_power=_to_float(data.get("thermal_power")),
electrical_power=_to_float(data.get("power_consumption")),
cop_instant=_to_float(data.get("cop_instant")),
cop_quality=data.get("cop_quality"),

# After (remove all four — these values don't exist in coordinator data
# or map to the wrong quantity):
thermal_power=None,
electrical_power=None,
cop_instant=None,
cop_quality=None,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/hitachi_yutaki/telemetry/collector.py tests/test_telemetry_collector.py
git commit -m "fix(telemetry): remove wrong power_consumption→electrical_power mapping

power_consumption (register 1098) is cumulative energy (kWh), not
instantaneous power. thermal_power and COP are computed by per-entity
domain services and not available in coordinator data. All three fields
are set to None — they can be recomputed server-side from the raw data
(water temps, flow, compressor current/frequency) already collected."
```

---

### Task 3: Mode FULL should also produce DailyStats

Currently `async_flush_telemetry()` branches exclusively: FULL sends MetricsBatch, BASIC sends DailyStats. FULL should be a superset of BASIC.

The flush happens every 5 minutes in FULL mode. We need a **day-level accumulator** that collects points across flush cycles and sends a proper daily aggregate once per day. Without this, we'd send partial-day stats every 5 minutes which would be misleading.

**Files:**
- Modify: `custom_components/hitachi_yutaki/coordinator.py`
- Modify: `tests/test_telemetry_integration.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_telemetry_integration.py`:

```python
class TestFullModeDailyStats:
    """Tests for FULL mode daily stats accumulation."""

    @pytest.mark.asyncio
    async def test_full_flush_sends_daily_stats_at_day_boundary(self):
        """FULL mode: daily stats sent when date changes."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.FULL)
        data = _sample_data()

        # Collect some points
        for _ in range(5):
            coordinator.telemetry_collector.collect(
                data, is_compressor_running=True, is_defrosting=False
            )

        # First flush: metrics sent, daily stats accumulated but not sent yet
        await coordinator.async_flush_telemetry()
        coordinator.telemetry_client.send_metrics.assert_called_once()

        # Verify daily points accumulated
        assert len(coordinator._daily_points_accumulator) == 5

    @pytest.mark.asyncio
    async def test_full_accumulates_points_across_flushes(self):
        """FULL mode: daily accumulator grows across multiple flushes."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.FULL)
        data = _sample_data()

        # First flush: 3 points
        for _ in range(3):
            coordinator.telemetry_collector.collect(
                data, is_compressor_running=True, is_defrosting=False
            )
        await coordinator.async_flush_telemetry()

        # Second flush: 2 more points
        for _ in range(2):
            coordinator.telemetry_collector.collect(
                data, is_compressor_running=True, is_defrosting=False
            )
        await coordinator.async_flush_telemetry()

        assert len(coordinator._daily_points_accumulator) == 5

    @pytest.mark.asyncio
    async def test_full_sends_daily_stats_on_date_change(self):
        """FULL mode: daily stats sent and accumulator reset when date changes."""
        from unittest.mock import patch
        from datetime import date as date_cls

        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.FULL)
        data = _sample_data()

        # Collect and flush on "day 1"
        with patch(
            "custom_components.hitachi_yutaki.coordinator.date"
        ) as mock_date:
            mock_date.today.return_value = date_cls(2026, 3, 18)
            mock_date.side_effect = lambda *a, **kw: date_cls(*a, **kw)

            for _ in range(5):
                coordinator.telemetry_collector.collect(
                    data, is_compressor_running=True, is_defrosting=False
                )
            await coordinator.async_flush_telemetry()

        # Now flush on "day 2" — should send daily stats for day 1
        with patch(
            "custom_components.hitachi_yutaki.coordinator.date"
        ) as mock_date:
            mock_date.today.return_value = date_cls(2026, 3, 19)
            mock_date.side_effect = lambda *a, **kw: date_cls(*a, **kw)

            coordinator.telemetry_collector.collect(
                data, is_compressor_running=True, is_defrosting=False
            )
            await coordinator.async_flush_telemetry()

        coordinator.telemetry_client.send_daily_stats.assert_called_once()
        stats = coordinator.telemetry_client.send_daily_stats.call_args[0][0]
        assert isinstance(stats, DailyStats)

        # Accumulator should have only today's point
        assert len(coordinator._daily_points_accumulator) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `_daily_points_accumulator` doesn't exist

- [ ] **Step 3: Implement daily accumulator in coordinator**

In `coordinator.py`, add to `__init__`:

```python
# Daily points accumulator for FULL-level daily stats
self._daily_points_accumulator: list[Any] = []
self._daily_stats_date: date | None = None
```

Update `async_flush_telemetry()`:

```python
async def async_flush_telemetry(self) -> None:
    """Flush telemetry buffer and send data."""
    if (
        self.telemetry_collector is None
        or self.telemetry_client is None
        or self._telemetry_meta is None
    ):
        _LOGGER.debug("Telemetry flush skipped: not configured")
        return

    points = self.telemetry_collector.flush()
    if not points:
        _LOGGER.debug("Telemetry flush: buffer empty, nothing to send")
        return

    instance_hash = self._telemetry_meta["instance_hash"]
    _LOGGER.debug(
        "Telemetry flush: %d points to send (level=%s)",
        len(points),
        self.telemetry_collector.level.value,
    )

    try:
        success = False
        if self.telemetry_collector.level == TelemetryLevel.FULL:
            # Send fine-grained metrics
            anonymized = [anonymize_metric_point(p) for p in points]
            batch = MetricsBatch(instance_hash=instance_hash, points=anonymized)
            success = await self.telemetry_client.send_metrics(batch)

            # Accumulate points for daily stats
            self._daily_points_accumulator.extend(points)

            # Send daily stats when date changes
            today = date.today()
            if self._daily_stats_date is not None and self._daily_stats_date != today:
                # Date changed — send yesterday's accumulated stats
                stats = aggregate_metrics(
                    instance_hash, self._daily_stats_date, self._daily_points_accumulator[:-len(points)]
                )
                anonymized_stats = anonymize_daily_stats(stats)
                await self.telemetry_client.send_daily_stats(anonymized_stats)
                # Reset accumulator with only today's points
                self._daily_points_accumulator = list(points)

            self._daily_stats_date = today

        elif self.telemetry_collector.level == TelemetryLevel.BASIC:
            stats = aggregate_metrics(instance_hash, date.today(), points)
            anonymized_stats = anonymize_daily_stats(stats)
            success = await self.telemetry_client.send_daily_stats(anonymized_stats)
            # Also refresh installation info daily
            await self._send_installation_info()

        if success:
            self.telemetry_last_send = datetime.now(tz=UTC)
            _LOGGER.debug("Telemetry flush: sent successfully")
        else:
            self.telemetry_send_failures += 1
            _LOGGER.warning("Telemetry flush: send returned failure")
    except Exception:
        self.telemetry_send_failures += 1
        _LOGGER.warning("Telemetry flush failed", exc_info=True)
```

**Note:** The accumulator grows in memory (~1 point per 5s = ~17K points/day, same as BASIC buffer). On HA restart, accumulated data is lost — this is acceptable; the continuous aggregate `metrics_daily_agg` in TimescaleDB provides the authoritative daily view.

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: All PASS (including existing `test_flush_full_sends_metrics_batch` which only checks `send_metrics`)

- [ ] **Step 5: Commit**

```bash
git add custom_components/hitachi_yutaki/coordinator.py tests/test_telemetry_integration.py
git commit -m "feat(telemetry): FULL mode accumulates and sends DailyStats at day boundary"
```

---

### Task 4: Wire register snapshot sending on first FULL-level poll

The `RegisterSnapshot` model, HTTP client method, Worker handler, and DB table all exist but no code calls `send_snapshot()`. The telemetry doc says "one-time register snapshot once after opt-in". We trigger it once on the first successful poll when level is FULL.

**Files:**
- Modify: `custom_components/hitachi_yutaki/coordinator.py`
- Modify: `tests/test_telemetry_integration.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_telemetry_integration.py`:

```python
class TestRegisterSnapshot:
    """Tests for one-time register snapshot on first FULL-level poll."""

    @pytest.mark.asyncio
    async def test_sends_snapshot_on_first_poll(self):
        """FULL level sends a register snapshot once."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.FULL)
        coordinator.telemetry_client.send_snapshot = AsyncMock(return_value=True)

        data = _sample_data()
        await coordinator._send_register_snapshot(data)

        coordinator.telemetry_client.send_snapshot.assert_called_once()
        snapshot = coordinator.telemetry_client.send_snapshot.call_args[0][0]
        assert snapshot.profile == "yutaki_s80"
        assert snapshot.gateway_type == "modbus_atw_mbs_02"
        assert snapshot.instance_hash == "a" * 64
        # Should contain numeric register values
        assert "outdoor_temp" in snapshot.registers
        assert snapshot.registers["outdoor_temp"] == 5.5

    @pytest.mark.asyncio
    async def test_snapshot_not_sent_twice(self):
        """Snapshot is only sent once (flag prevents re-send)."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.FULL)
        coordinator.telemetry_client.send_snapshot = AsyncMock(return_value=True)
        coordinator._snapshot_sent = True  # Already sent

        data = _sample_data()
        await coordinator._send_register_snapshot(data)

        coordinator.telemetry_client.send_snapshot.assert_not_called()

    @pytest.mark.asyncio
    async def test_snapshot_excludes_non_register_keys(self):
        """Snapshot should not include 'is_available' or non-numeric values."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.FULL)
        coordinator.telemetry_client.send_snapshot = AsyncMock(return_value=True)

        data = _sample_data()
        await coordinator._send_register_snapshot(data)

        snapshot = coordinator.telemetry_client.send_snapshot.call_args[0][0]
        assert "is_available" not in snapshot.registers
        # String values like operation_state should be excluded
        assert "operation_state" not in snapshot.registers

    @pytest.mark.asyncio
    async def test_snapshot_failure_is_silent(self):
        """Failed snapshot send doesn't raise, doesn't set flag."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.FULL)
        coordinator.telemetry_client.send_snapshot = AsyncMock(
            side_effect=Exception("network error")
        )

        data = _sample_data()
        await coordinator._send_register_snapshot(data)

        assert not coordinator._snapshot_sent
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `_send_register_snapshot` doesn't exist

- [ ] **Step 3: Implement snapshot sending**

In `coordinator.py`, add to `__init__`:

```python
self._snapshot_sent: bool = False
```

Add the import at the top of the file (with the other telemetry imports):

```python
from .telemetry import (
    ...
    RegisterSnapshot,  # add this
)
```

Add a new method to `HitachiYutakiDataCoordinator`:

```python
async def _send_register_snapshot(self, data: dict[str, Any]) -> None:
    """Send a one-time register snapshot (FULL level only)."""
    if self._snapshot_sent:
        return

    meta = self._telemetry_meta
    if meta is None or self.telemetry_client is None:
        return

    # Build register dict: only numeric values, skip meta keys
    registers: dict[str, float] = {}
    for key, value in data.items():
        if key == "is_available":
            continue
        if isinstance(value, (int, float)):
            registers[key] = value

    snapshot = RegisterSnapshot(
        instance_hash=meta["instance_hash"],
        time=datetime.now(tz=UTC),
        profile=meta["profile"],
        gateway_type=meta["gateway_type"],
        registers=registers,
    )

    try:
        await self.telemetry_client.send_snapshot(snapshot)
        self._snapshot_sent = True
        _LOGGER.debug("Telemetry: register snapshot sent")
    except Exception:
        _LOGGER.debug("Failed to send register snapshot", exc_info=True)
```

**Note:** `RegisterSnapshot.registers` is typed as `dict[str, int]` in models.py but the actual register values include floats (temperatures). Update the type annotation in `models.py:297` from `dict[str, int]` to `dict[str, float]` for correctness.

In `_async_update_data()`, after the installation info block (after line 132), add:

```python
# Send register snapshot once (FULL level only)
if (
    not self._snapshot_sent
    and self.telemetry_collector is not None
    and self.telemetry_collector.level == TelemetryLevel.FULL
    and self.telemetry_client is not None
    and self._telemetry_meta is not None
):
    await self._send_register_snapshot(data)
```

Also update `models.py` line 297:
```python
# Before:
registers: dict[str, int]
# After:
registers: dict[str, float]
```

And update `backend/worker/src/types.ts` line 135:
```typescript
// Before:
registers: Record<string, number>;
// After (no change needed — TypeScript 'number' already covers int and float):
registers: Record<string, number>;
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/hitachi_yutaki/coordinator.py custom_components/hitachi_yutaki/telemetry/models.py tests/test_telemetry_integration.py
git commit -m "feat(telemetry): send register snapshot once on first FULL-level poll"
```

---

### Task 5: Run full quality checks

- [ ] **Step 1: Run lint**

Run: `make check`
Expected: No errors

- [ ] **Step 2: Run full test suite**

Run: `make test`
Expected: All tests pass

- [ ] **Step 3: Fix any issues, commit if needed**

```bash
git add -u
git commit -m "fix(telemetry): lint and test fixups"
```
