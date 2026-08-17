# Per-gateway telemetry identity (`device_hash`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each heat-pump unit its own telemetry identity so the rate limit, the R2 archive and the fleet dashboard address a machine rather than a household, fixing the permanent 429 loop reported in [#395](https://github.com/alepee/hass-hitachi_yutaki/issues/395).

**Architecture:** Additive change. `instance_hash` stays in every payload untouched; a new `device_hash = sha256(f"{instance_id}:{entry.unique_id}")` joins it. The Worker keys its rate limit and R2 object names on `device_hash`, falling back to `instance_hash` when the field is absent so legacy clients keep byte-identical behaviour. WAE keeps `instance_hash` as its index and gains `device_hash` as an appended blob, so existing Grafana queries are untouched.

**Tech Stack:** Python 3.13 / Home Assistant custom component (pytest, `pytest-homeassistant-custom-component`, ruff); Cloudflare Worker in TypeScript (vitest, wrangler).

**Design doc:** [`docs/superpowers/specs/2026-08-15-telemetry-per-gateway-identity-design.md`](../specs/2026-08-15-telemetry-per-gateway-identity-design.md)

## Global Constraints

- **Work in a dedicated git worktree.** The shared checkout at `/Users/alepee/Documents/Perso/homeassistant/integrations/hass-hitachi_yutaki` is on `fix/power-entity-ignored-when-current-zero` and holds another session's uncommitted changes (`adapters/derived_metrics.py`, `profiles/yutampo_r32.py`, `tests/adapters/test_derived_metrics.py`, `CHANGELOG.md`, `docs/reference/domain-services.md`, `docs/gateway/hc-a-mb.md`). Never commit, stage, or switch branches **in that directory** — it would capture or displace work that is not ours. A worktree created from `main` is a separate directory and leaves those changes untouched, so there is no need to wait for that work to land.
- **Expect one merge conflict.** That other branch also edits `CHANGELOG.md` and `docs/reference/domain-services.md`, which Task 8 touches. Whichever PR merges second resolves it. This is a normal conflict, not a reason to reorder the work.
- Branch name: `fix/395-telemetry-per-gateway-identity`.
- **Domain layer purity does not apply here** — `telemetry/` is an infrastructure package, not `domain/`. It may use stdlib and `aiohttp`, but still must not import `homeassistant.*` (only `coordinator.py` and `__init__.py` may).
- Type hints required on every function signature; docstrings required on every public function and class (`AGENT.md`, Code Quality Standards).
- Import aliases must follow `[tool.ruff.lint.flake8-import-conventions.extend-aliases]` in `pyproject.toml`.
- No `Co-Authored-By:` trailers in commit messages. Conventional-commit style (`fix:`, `feat:`, `test:`, `docs:`).
- Every behaviour-affecting change needs a `CHANGELOG.md` entry under `[Unreleased]` (Task 8 covers this once, for the whole feature).
- Python commands: `make test` (full suite), `make check` (lint + format). Worker commands: `cd backend/worker && npx vitest run` (plain `npm test` starts watch mode and will hang an agent).
- Exact hash formula, used verbatim everywhere: `sha256(f"{instance_id}:{unique_id}")`, lowercase hex.
- `MAX_POINT_AGE = timedelta(minutes=30)`.

---

### Task 1: `device_hash` derivation and payload models

**Files:**
- Modify: `custom_components/hitachi_yutaki/telemetry/anonymizer.py:12-14`
- Modify: `custom_components/hitachi_yutaki/telemetry/models.py:17-108`
- Modify: `custom_components/hitachi_yutaki/coordinator.py:308-322`, `:348-354`, `:374`
- Modify: `custom_components/hitachi_yutaki/__init__.py:337`, `:412-432`
- Test: `tests/test_telemetry_anonymizer.py`, `tests/test_telemetry_models.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `hash_device_id(instance_id: str, unique_id: str) -> str` in `telemetry/anonymizer.py`
  - `InstallationInfo.device_hash`, `MetricsBatch.device_hash`, `RegisterSnapshot.device_hash` — all `str`, all declared immediately after `instance_hash`, all emitted by `to_dict()` under the key `"device_hash"`.
  - `coordinator._telemetry_meta["device_hash"]: str`

- [ ] **Step 1: Write the failing tests for the hash helper**

Append to `tests/test_telemetry_anonymizer.py`:

```python
class TestHashDeviceId:
    """Tests for per-config-entry device hashing."""

    def test_returns_lowercase_sha256_hex(self):
        """Device hash is a 64-char lowercase hex digest."""
        result = hash_device_id("instance-abc", "hitachi_yutaki_ABC123_1")
        assert len(result) == 64
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)

    def test_is_stable(self):
        """Same inputs always produce the same hash."""
        a = hash_device_id("instance-abc", "hitachi_yutaki_ABC123_1")
        b = hash_device_id("instance-abc", "hitachi_yutaki_ABC123_1")
        assert a == b

    def test_differs_per_entry_on_same_instance(self):
        """Two entries of one HA instance get distinct identities.

        This is the whole point of #395: instance_hash was shared, so all
        entries collided on the server-side rate limit.
        """
        a = hash_device_id("instance-abc", "hitachi_yutaki_ABC123_1")
        b = hash_device_id("instance-abc", "hitachi_yutaki_ABC123_2")
        assert a != b

    def test_differs_across_instances_for_same_hardware(self):
        """Salting with instance_id keeps two households uncorrelatable."""
        a = hash_device_id("instance-abc", "hitachi_yutaki_ABC123_1")
        b = hash_device_id("instance-xyz", "hitachi_yutaki_ABC123_1")
        assert a != b

    def test_never_equals_the_instance_hash(self):
        """Device and instance identities are always distinct values."""
        assert hash_device_id("instance-abc", "u1") != hash_instance_id("instance-abc")
```

Add `hash_device_id` to the existing import of `hash_instance_id` at the top of the file.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_telemetry_anonymizer.py -v`
Expected: FAIL with `ImportError: cannot import name 'hash_device_id'`

- [ ] **Step 3: Implement the hash helper**

In `custom_components/hitachi_yutaki/telemetry/anonymizer.py`, directly after `hash_instance_id`:

```python
def hash_device_id(instance_id: str, unique_id: str) -> str:
    """Hash an (HA instance, config entry) pair with SHA-256 (non-reversible).

    Identifies a single heat-pump unit rather than a household. Salting with
    the instance id keeps the value uncorrelatable across HA instances, so two
    users behind the same gateway hardware cannot be linked (#395).
    """
    return hashlib.sha256(f"{instance_id}:{unique_id}".encode()).hexdigest()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_telemetry_anonymizer.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing tests for the payload models**

Append to `tests/test_telemetry_models.py`:

```python
class TestDeviceHashInPayloads:
    """Every payload type carries both identities (#395)."""

    def test_installation_emits_both_hashes(self):
        """Installation payload carries instance_hash and device_hash."""
        info = InstallationInfo(
            instance_hash="a" * 64,
            device_hash="b" * 64,
            profile="yutaki_s80",
            gateway_type="modbus_atw_mbs_02",
            ha_version="2026.8.0",
            integration_version="2.2.0",
            power_supply="single",
            has_dhw=True,
            has_pool=False,
            has_cooling=True,
            max_circuits=2,
            has_secondary_compressor=True,
        )
        payload = info.to_dict()
        assert payload["instance_hash"] == "a" * 64
        assert payload["device_hash"] == "b" * 64

    def test_metrics_emits_both_hashes(self):
        """Metrics batch carries instance_hash and device_hash."""
        payload = MetricsBatch(
            instance_hash="a" * 64,
            device_hash="b" * 64,
            points=[{"time": datetime(2026, 8, 15, tzinfo=UTC), "outdoor_temp": 5.0}],
        ).to_dict()
        assert payload["instance_hash"] == "a" * 64
        assert payload["device_hash"] == "b" * 64

    def test_snapshot_emits_both_hashes(self):
        """Register snapshot carries instance_hash and device_hash."""
        payload = RegisterSnapshot(
            instance_hash="a" * 64,
            device_hash="b" * 64,
            time=datetime(2026, 8, 15, tzinfo=UTC),
            profile="yutaki_s80",
            gateway_type="modbus_atw_mbs_02",
            registers={"outdoor_temp": 5.0},
        ).to_dict()
        assert payload["instance_hash"] == "a" * 64
        assert payload["device_hash"] == "b" * 64
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `uv run pytest tests/test_telemetry_models.py -v`
Expected: FAIL with `TypeError: ... unexpected keyword argument 'device_hash'`

- [ ] **Step 7: Add the field to the three dataclasses**

In `telemetry/models.py`, add `device_hash: str` immediately after `instance_hash: str` in `InstallationInfo`, `MetricsBatch` and `RegisterSnapshot`.

Position matters: `MetricsBatch.points` has a default (`field(default_factory=list)`) and `InstallationInfo.latitude`/`longitude`/`climate_zone` have defaults, so a new required field must be declared before them or Python raises `TypeError: non-default argument follows default argument`.

Then add the key to each `to_dict()`, next to `instance_hash`:

```python
# InstallationInfo.to_dict()
return {
    "type": "installation",
    "instance_hash": self.instance_hash,
    "device_hash": self.device_hash,
    "data": data,
}

# MetricsBatch.to_dict()
return {
    "type": "metrics",
    "instance_hash": self.instance_hash,
    "device_hash": self.device_hash,
    "points": serialized_points,
}

# RegisterSnapshot.to_dict()
return {
    "type": "snapshot",
    "instance_hash": self.instance_hash,
    "device_hash": self.device_hash,
    "time": self.time.isoformat(),
    "profile": self.profile,
    "gateway_type": self.gateway_type,
    "registers": self.registers,
}
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest tests/test_telemetry_models.py -v`
Expected: PASS

- [ ] **Step 9: Wire the derivation into setup**

In `custom_components/hitachi_yutaki/__init__.py`:

Extend the import at line 67:

```python
from .telemetry.anonymizer import hash_device_id, hash_instance_id
```

Fix the `unique_id` back-fill at line 337 so it matches the config flow's format (`config_flow.py:365`), which includes the unit id:

```python
unique_id = f"{DOMAIN}_{hw_id}_{entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)}"
```

`CONF_UNIT_ID` and `DEFAULT_UNIT_ID` are already imported and used at line 319, so no new import is needed.

Then, after line 413 (`instance_hash = hash_instance_id(instance_id)`):

```python
# Per-unit identity. entry.unique_id is guaranteed non-None here: the
# back-fill above runs before this point. Keyed on the hardware identifier
# so deleting and re-adding an entry preserves the unit's fleet history.
device_hash = hash_device_id(instance_id, entry.unique_id)
```

And add it to the meta dict at line 425:

```python
coordinator._telemetry_meta = {
    "instance_hash": instance_hash,
    "device_hash": device_hash,
    "profile": profile_key,
    ...
}
```

- [ ] **Step 10: Pass it through the three payload builders**

In `custom_components/hitachi_yutaki/coordinator.py`, add `device_hash=meta["device_hash"],` immediately after each `instance_hash=` line:

- `_send_installation_info`, line 309
- `_send_register_snapshot`, line 349
- `async_flush_telemetry`, line 374 — this one reads from a local, so add alongside it:

```python
instance_hash = self._telemetry_meta["instance_hash"]
device_hash = self._telemetry_meta["device_hash"]
...
batch = MetricsBatch(
    instance_hash=instance_hash, device_hash=device_hash, points=anonymized
)
```

- [ ] **Step 11: Run the full suite and lint**

Run: `make test && make check`
Expected: PASS.

Existing tests construct these dataclasses positionally or by keyword and will fail with `TypeError: missing required positional argument: 'device_hash'`. Add `device_hash="b" * 64` to every construction. Known sites, to be re-checked with `rg -n 'InstallationInfo\(|MetricsBatch\(|RegisterSnapshot\(' tests/`:

- `tests/test_telemetry_http_client.py:56` — the `_make_installation()` helper. Task 2 depends on this one.
- `tests/test_telemetry_models.py` — the existing `_make_info()` helper and its siblings.
- `tests/test_telemetry_anonymizer.py` — `anonymize_installation_info` fixtures.
- `tests/test_telemetry_integration.py`, `tests/test_coordinator_installation_resend.py`.

- [ ] **Step 12: Commit**

```bash
git add custom_components/hitachi_yutaki/telemetry/anonymizer.py \
        custom_components/hitachi_yutaki/telemetry/models.py \
        custom_components/hitachi_yutaki/coordinator.py \
        custom_components/hitachi_yutaki/__init__.py \
        tests/test_telemetry_anonymizer.py \
        tests/test_telemetry_models.py
git commit -m "feat: derive a per-config-entry device_hash for telemetry"
```

---

### Task 2: Diagnosable telemetry failures

**Files:**
- Modify: `custom_components/hitachi_yutaki/telemetry/http_client.py:31-40`, `:78-86`
- Modify: `custom_components/hitachi_yutaki/coordinator.py:377-384`
- Modify: `custom_components/hitachi_yutaki/__init__.py:418`
- Test: `tests/test_telemetry_http_client.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `HttpTelemetryClient(session, instance_hash, endpoint=TELEMETRY_ENDPOINT, label="")` — `label` is the config entry title, prefixed onto every log line as `"[<label>] "`.

- [ ] **Step 1: Write the failing tests**

First extend the existing `_make_client` helper at `tests/test_telemetry_http_client.py:25` so it can pass a label:

```python
def _make_client(
    session: aiohttp.ClientSession | None = None,
    instance_hash: str = "abc123",
    endpoint: str = "https://test.example.com/v1/ingest",
    label: str = "",
) -> HttpTelemetryClient:
    """Create a client with optional mock session."""
    return HttpTelemetryClient(
        session=session or MagicMock(spec=aiohttp.ClientSession),
        instance_hash=instance_hash,
        endpoint=endpoint,
        label=label,
    )
```

Then append, reusing the file's existing `_mock_response`, `_mock_session` and `_make_installation` helpers (`_make_installation` already carries `device_hash` after Task 1):

```python
class TestDiagnosability:
    """Failures must name their cause and their config entry (#395)."""

    async def test_429_is_logged_at_warning(self, caplog):
        """A 429 must be visible: it was DEBUG, which made #395 undiagnosable."""
        client = _make_client(
            _mock_session(_mock_response(429, "Rate limit exceeded")), label="PAC 1"
        )
        with caplog.at_level(logging.DEBUG):
            assert await client.send_installation(_make_installation()) is False
        rejections = [r for r in caplog.records if "Telemetry rejected" in r.message]
        assert len(rejections) == 1
        assert rejections[0].levelno == logging.WARNING
        assert "429" in caplog.text

    async def test_log_line_carries_the_entry_label(self, caplog):
        """Multi-gateway installs must be able to tell their entries apart."""
        client = _make_client(
            _mock_session(_mock_response(429, "Rate limit exceeded")), label="ECS 2"
        )
        with caplog.at_level(logging.WARNING):
            await client.send_installation(_make_installation())
        assert "[ECS 2]" in caplog.text

    async def test_label_is_optional(self, caplog):
        """Without a label the message has no stray prefix."""
        client = _make_client(_mock_session(_mock_response(400, "Bad payload")))
        with caplog.at_level(logging.WARNING):
            await client.send_installation(_make_installation())
        assert "[]" not in caplog.text
        assert "Telemetry rejected (HTTP 400)" in caplog.text
```

Add `import logging` to the file's imports. `caplog.at_level(logging.DEBUG)` in the first test is deliberate: it proves the message is emitted at WARNING even when DEBUG is capturable, which is exactly the distinction the reporter could not make.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_telemetry_http_client.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'label'`, and the 429 assertion fails because the branch logs at DEBUG.

- [ ] **Step 3: Add the label and raise the 429 severity**

In `telemetry/http_client.py`, extend the constructor:

```python
    def __init__(
        self,
        session: aiohttp.ClientSession,
        instance_hash: str,
        endpoint: str = TELEMETRY_ENDPOINT,
        label: str = "",
    ) -> None:
        """Initialize the HTTP telemetry client.

        `label` is the config entry title. It prefixes every log line so a
        multi-gateway installation can tell which entry failed (#395).
        """
        self._session = session
        self._instance_hash = instance_hash
        self._endpoint = endpoint
        self._prefix = f"[{label}] " if label else ""
```

Replace the 4xx branch (lines 78-86) with:

```python
                    # Client errors (4xx) are not retryable. All are logged at
                    # WARNING, including 429: with per-unit identities a rate
                    # limit means something is genuinely wrong, and hiding it
                    # at DEBUG is what made #395 undiagnosable for the reporter.
                    if 400 <= resp.status < 500:
                        _LOGGER.warning(
                            "%sTelemetry rejected (HTTP %s): %s",
                            self._prefix,
                            resp.status,
                            await resp.text(),
                        )
                        return False
```

Prefix the remaining log calls in the file the same way — the three DEBUG branches (server error, timeout, client error) and the final `"Telemetry send failed after %d attempts"` warning, each gaining `self._prefix` as its first `%s` argument.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_telemetry_http_client.py -v`
Expected: PASS

- [ ] **Step 5: Pass the label at construction and label the coordinator warnings**

In `__init__.py`, line 418:

```python
        coordinator.telemetry_client = HttpTelemetryClient(
            session, instance_hash, label=entry.title
        )
```

In `coordinator.py`, `async_flush_telemetry`, replace the two warnings:

```python
            else:
                self.telemetry_send_failures += 1
                _LOGGER.warning(
                    "[%s] Telemetry flush: send returned failure",
                    self.config_entry.title,
                )
        except Exception:
            self.telemetry_send_failures += 1
            _LOGGER.warning(
                "[%s] Telemetry flush failed",
                self.config_entry.title,
                exc_info=True,
            )
```

`self.config_entry` is set by `DataUpdateCoordinator.__init__`, which already receives `config_entry=entry` (`coordinator.py:96-99`).

- [ ] **Step 6: Run the full suite and lint**

Run: `make test && make check`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add custom_components/hitachi_yutaki/telemetry/http_client.py \
        custom_components/hitachi_yutaki/coordinator.py \
        custom_components/hitachi_yutaki/__init__.py \
        tests/test_telemetry_http_client.py
git commit -m "fix: make telemetry send failures diagnosable per config entry"
```

---

### Task 3: Re-queue buffered points instead of dropping them

**Files:**
- Modify: `custom_components/hitachi_yutaki/telemetry/collector.py:1-69`
- Modify: `custom_components/hitachi_yutaki/coordinator.py:364-384`
- Test: `tests/test_telemetry_collector.py`, `tests/test_coordinator.py`

**Interfaces:**
- Consumes: `HttpTelemetryClient` label behaviour from Task 2 (log assertions only).
- Produces: `TelemetryCollector.requeue(points: list[dict]) -> None`, and the module constant `MAX_POINT_AGE: timedelta`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_telemetry_collector.py`:

```python
class TestRequeue:
    """Failed sends put their points back (#395)."""

    def test_requeued_points_are_returned_by_the_next_flush(self):
        """A failed batch is not lost."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        points = collector.flush()
        assert collector.buffer_size == 0

        collector.requeue(points)
        assert collector.buffer_size == 1
        assert collector.flush() == points

    def test_requeued_points_come_before_newer_ones(self):
        """Chronological order is preserved across a failed send."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data(outdoor_temp=1.0))
        failed = collector.flush()
        collector.collect(_sample_data(outdoor_temp=2.0))

        collector.requeue(failed)
        result = collector.flush()
        assert [p["outdoor_temp"] for p in result] == [1.0, 2.0]

    def test_stale_points_are_dropped(self):
        """Points older than MAX_POINT_AGE have no analytical value.

        This is also the guard that stops a broken installation from
        replaying garbage forever: when a gateway loses its unit every
        register reads 0xFFFF, and those points are collected as valid.
        """
        collector = TelemetryCollector(TelemetryLevel.ON)
        stale = dict(_sample_data())
        stale["time"] = datetime.now(tz=UTC) - MAX_POINT_AGE - timedelta(seconds=1)
        fresh = dict(_sample_data())
        fresh["time"] = datetime.now(tz=UTC)

        collector.requeue([stale, fresh])
        assert collector.buffer_size == 1
        assert collector.flush() == [fresh]

    def test_overflow_keeps_the_newest_points(self):
        """Regression guard: deque.extendleft evicts the NEWEST points.

        appendleft/extendleft on a bounded deque drop from the right, which
        is the opposite of what is wanted here, so requeue must rebuild the
        buffer explicitly.
        """
        collector = TelemetryCollector(TelemetryLevel.ON, buffer_max_size=3)
        for i in range(3):
            collector.collect(_sample_data(outdoor_temp=float(i)))

        old = [{**_sample_data(outdoor_temp=-1.0), "time": datetime.now(tz=UTC)}]
        collector.requeue(old)

        assert collector.buffer_size == 3
        assert [p["outdoor_temp"] for p in collector.flush()] == [0.0, 1.0, 2.0]

    def test_requeue_of_an_empty_list_is_a_noop(self):
        """Nothing to put back, nothing changes."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        collector.requeue([])
        assert collector.buffer_size == 1
```

Add `datetime`, `timedelta` and `MAX_POINT_AGE` to the imports at the top of the file.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_telemetry_collector.py -v`
Expected: FAIL with `ImportError: cannot import name 'MAX_POINT_AGE'`

- [ ] **Step 3: Implement `requeue`**

In `telemetry/collector.py`, add to the imports and constants:

```python
from datetime import UTC, datetime, timedelta

# Re-queued points older than this are dropped. Matches the buffer's natural
# window (360 points at a 5s poll interval) and bounds how long a broken
# installation can keep replaying failed sends (#395).
MAX_POINT_AGE = timedelta(minutes=30)
```

Add the method after `flush`:

```python
    def requeue(self, points: list[dict[str, Any]]) -> None:
        """Put previously flushed points back at the front of the buffer.

        Called when a send fails, so the batch is retried on the next flush
        instead of being lost. Two bounds apply: points older than
        MAX_POINT_AGE are dropped, and on overflow the newest points win.

        The explicit rebuild is deliberate. `deque.extendleft` on a bounded
        deque evicts from the right, i.e. the newest points — the opposite of
        the intended policy.
        """
        if not points:
            return

        cutoff = datetime.now(tz=UTC) - MAX_POINT_AGE
        kept = [p for p in points if p.get("time") is not None and p["time"] >= cutoff]
        if not kept:
            return

        maxlen = self._buffer.maxlen
        merged = kept + list(self._buffer)
        self._buffer = deque(merged[-maxlen:] if maxlen else merged, maxlen=maxlen)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_telemetry_collector.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing coordinator test**

Append to `tests/test_coordinator.py`, following that file's existing coordinator fixture:

```python
async def test_failed_flush_requeues_points(coordinator):
    """A rejected batch stays in the buffer for the next cycle (#395)."""
    coordinator.telemetry_collector = TelemetryCollector(TelemetryLevel.ON)
    coordinator.telemetry_collector.collect({"is_available": True, "outdoor_temp": 5.0})
    coordinator._telemetry_meta = {"instance_hash": "a" * 64, "device_hash": "b" * 64}
    coordinator.telemetry_client = AsyncMock()
    coordinator.telemetry_client.send_metrics.return_value = False

    await coordinator.async_flush_telemetry()

    assert coordinator.telemetry_collector.buffer_size == 1
    assert coordinator.telemetry_send_failures == 1


async def test_successful_flush_does_not_requeue(coordinator):
    """A delivered batch is discarded, not resent."""
    coordinator.telemetry_collector = TelemetryCollector(TelemetryLevel.ON)
    coordinator.telemetry_collector.collect({"is_available": True, "outdoor_temp": 5.0})
    coordinator._telemetry_meta = {"instance_hash": "a" * 64, "device_hash": "b" * 64}
    coordinator.telemetry_client = AsyncMock()
    coordinator.telemetry_client.send_metrics.return_value = True

    await coordinator.async_flush_telemetry()

    assert coordinator.telemetry_collector.buffer_size == 0
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `uv run pytest tests/test_coordinator.py -k requeue -v`
Expected: FAIL — `buffer_size` is 0, because the points were dropped.

- [ ] **Step 7: Re-queue on both failure paths**

In `coordinator.py`, `async_flush_telemetry`, add the re-queue to the `else` branch and to the `except` branch. The `except` branch re-queues the original `points`, because `anonymized` may never have been bound:

```python
            if success:
                self.telemetry_last_send = datetime.now(tz=UTC)
            else:
                self.telemetry_send_failures += 1
                self.telemetry_collector.requeue(points)
                _LOGGER.warning(
                    "[%s] Telemetry flush: send returned failure",
                    self.config_entry.title,
                )
        except Exception:
            self.telemetry_send_failures += 1
            self.telemetry_collector.requeue(points)
            _LOGGER.warning(
                "[%s] Telemetry flush failed",
                self.config_entry.title,
                exc_info=True,
            )
```

- [ ] **Step 8: Run the full suite and lint**

Run: `make test && make check`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add custom_components/hitachi_yutaki/telemetry/collector.py \
        custom_components/hitachi_yutaki/coordinator.py \
        tests/test_telemetry_collector.py \
        tests/test_coordinator.py
git commit -m "fix: re-queue telemetry points when a send fails"
```

---

### Task 4: Worker accepts an optional `device_hash`

**Files:**
- Modify: `backend/worker/src/types.ts:8-11`
- Modify: `backend/worker/src/validator.ts:74-237`
- Modify: `backend/worker/src/index.ts:47-48`
- Test: `backend/worker/test/index.test.ts`

**Interfaces:**
- Consumes: the payload shape produced by Task 1 (`device_hash` as a top-level string key).
- Produces:
  - `BasePayload.device_hash: string` — always populated; equals `instance_hash` for legacy payloads.
  - `ValidationResult { payload: TelemetryPayload; hasExplicitDeviceHash: boolean }`
  - `validate(raw: string, instanceHashHeader: string | null): ValidationResult`

`hasExplicitDeviceHash` is returned alongside the payload rather than stored on it, because `archiveToR2` does `JSON.stringify(payload)` and an internal protocol flag must not leak into the archived JSON.

- [ ] **Step 1: Write the failing tests**

Append to `backend/worker/test/index.test.ts`. Reuse that file's existing helpers rather than inventing new ones: `createFakeCache`, `createFakeBucket`, `createFakeAE`, `makeEnv(bucket)`, `makeRequest(body: object)` (which already sets the `x-instance-hash` header), `metricsPayload()`, the `HASH` constant, and the `beforeEach` that installs `globalThis.caches`.

Add two module-level helpers next to `metricsPayload`:

```ts
const DEVICE = "c".repeat(64);

function installationPayload() {
  return {
    type: "installation",
    instance_hash: HASH,
    data: { profile: "yutaki_s80", gateway_type: "modbus_atw_mbs_02" },
  };
}
```

Then:

```ts
describe("device_hash validation (#395)", () => {
  it("accepts a payload without device_hash (legacy client)", async () => {
    const bucket = createFakeBucket();
    const res = await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));
    expect(res.status).toBe(202);
  });

  it("accepts a valid device_hash", async () => {
    const bucket = createFakeBucket();
    const res = await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );
    expect(res.status).toBe(202);
  });

  it("rejects a malformed device_hash with 400", async () => {
    const bucket = createFakeBucket();
    const res = await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: "not-a-hash" }),
      makeEnv(bucket),
    );
    expect(res.status).toBe(400);
    expect(await res.text()).toContain("device_hash");
  });

  it("archives device_hash without leaking the internal flag", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );
    const archived = JSON.parse(bucket.put.mock.calls[0][1] as string);
    expect(archived.device_hash).toBe(DEVICE);
    expect(archived).not.toHaveProperty("hasExplicitDeviceHash");
    expect(archived).not.toHaveProperty("has_explicit_device_hash");
  });

  it("falls back to the instance identity for a legacy payload", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));
    const archived = JSON.parse(bucket.put.mock.calls[0][1] as string);
    expect(archived.device_hash).toBe(HASH);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend/worker && npx vitest run`
Expected: FAIL — the malformed-hash case returns 202 instead of 400, and `archived.device_hash` is `undefined`.

- [ ] **Step 3: Add the field to the payload types**

In `backend/worker/src/types.ts`:

```ts
/** Base payload with type discriminator. */
export interface BasePayload {
  type: string;
  instance_hash: string;
  /** Per-unit identity (#395). Equals instance_hash for legacy clients. */
  device_hash: string;
}
```

- [ ] **Step 4: Parse and validate it**

In `backend/worker/src/validator.ts`, add the result type near `ValidationError`:

```ts
/** A validated payload plus the protocol facts the caller needs. */
export interface ValidationResult {
  payload: TelemetryPayload;
  /** True when the client sent device_hash itself (selects the key layout). */
  hasExplicitDeviceHash: boolean;
}
```

In `validate()`, after the `instance_hash` header cross-check and before the `type` switch:

```ts
  // Per-unit identity (#395). Optional: legacy clients never send it, and
  // fall back to the instance identity so their behaviour is unchanged.
  let deviceHash = instanceHash;
  let hasExplicitDeviceHash = false;
  if (payload.device_hash !== undefined) {
    const dh = String(payload.device_hash);
    if (!INSTANCE_HASH_RE.test(dh)) {
      throw new ValidationError("Invalid device_hash (expected SHA-256 hex)");
    }
    deviceHash = dh;
    hasExplicitDeviceHash = true;
  }
```

Thread `deviceHash` into each `validateX(payload, instanceHash, deviceHash)` helper, which adds `device_hash: deviceHash,` next to `instance_hash` in its returned object. Wrap each switch arm so `validate` returns `{ payload: ..., hasExplicitDeviceHash }`.

- [ ] **Step 5: Update the single call site**

In `backend/worker/src/index.ts`, line 47-48:

```ts
      const instanceHashHeader = request.headers.get("x-instance-hash");
      const { payload } = validate(body, instanceHashHeader);
```

Destructure **only** `payload` here. `tsconfig.json` sets `noUnusedLocals: true`, so binding `hasExplicitDeviceHash` before Task 6 consumes it would fail `tsc`. Task 6 widens this line.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend/worker && npx vitest run`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/worker/src/types.ts backend/worker/src/validator.ts \
        backend/worker/src/index.ts backend/worker/test/index.test.ts
git commit -m "feat(worker): accept an optional per-unit device_hash"
```

---

### Task 5: Rate limit per unit

**Files:**
- Modify: `backend/worker/src/rate-limiter.ts:1-77`
- Modify: `backend/worker/src/index.ts:50-53`, `:80`
- Test: `backend/worker/test/rate-limiter.test.ts`, `backend/worker/test/index.test.ts`

**Interfaces:**
- Consumes: `payload.device_hash` from Task 4.
- Produces: `isRateLimited(deviceHash: string, payloadType: string): Promise<boolean>` and `markRateLimit(deviceHash: string, payloadType: string): Promise<void>` — same signatures as today, keyed on the device identity.

- [ ] **Step 1: Write the failing tests**

Append to `backend/worker/test/index.test.ts`:

```ts
describe("per-unit rate limiting (#395)", () => {
  it("lets two units of one instance send within the same window", async () => {
    const env = makeEnv(createFakeBucket());
    const deviceB = "d".repeat(64);

    const first = await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      env,
    );
    const second = await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: deviceB }),
      env,
    );

    expect(first.status).toBe(202);
    expect(second.status).toBe(202);
  });

  it("still rate limits a single unit", async () => {
    const env = makeEnv(createFakeBucket());

    await worker.fetch(makeRequest({ ...metricsPayload(), device_hash: DEVICE }), env);
    const second = await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      env,
    );

    expect(second.status).toBe(429);
  });

  it("still rate limits a legacy client against itself", async () => {
    const env = makeEnv(createFakeBucket());

    await worker.fetch(makeRequest(metricsPayload()), env);
    const second = await worker.fetch(makeRequest(metricsPayload()), env);

    expect(second.status).toBe(429);
  });
});
```

The file's existing `beforeEach` already reinstalls a fresh `createFakeCache` onto `globalThis.caches` per test, so the two requests within one test share a store while tests stay isolated. Do not add another.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend/worker && npx vitest run`
Expected: FAIL — the first test gets 429 on the second request, because the key is still the shared instance hash.

- [ ] **Step 3: Key the limiter on the device identity**

In `backend/worker/src/rate-limiter.ts`, rename the `instanceHash` parameter to `deviceHash` in `cacheKeyFor`, `isRateLimited` and `markRateLimit`, and update the file's header comment:

```ts
/**
 * Per-device-hash + payload-type rate limiting using Cloudflare Cache API.
 * Limit: 1 request per minute per (device_hash, payload_type).
 *
 * device_hash identifies a single heat-pump unit. Before #395 the key was the
 * instance hash, shared by every config entry on one HA instance, so a
 * multi-gateway installation rejected all but one flush per cycle forever.
 * Legacy clients send no device_hash and fall back to the instance hash, so
 * their cache key is byte-identical to what it was.
 * ...
 */
```

In `backend/worker/src/index.ts`, lines 53 and 80:

```ts
      if (await isRateLimited(payload.device_hash, payload.type)) {
```

```ts
        await markRateLimit(payload.device_hash, payload.type);
```

Update the inline comment at line 50 to say `(device_hash + payload type)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend/worker && npx vitest run`
Expected: PASS, including the existing `rate-limiter.test.ts` cases (the signature is unchanged, only the parameter name).

- [ ] **Step 5: Commit**

```bash
git add backend/worker/src/rate-limiter.ts backend/worker/src/index.ts \
        backend/worker/test/index.test.ts
git commit -m "fix(worker): rate limit per heat-pump unit, not per HA instance"
```

---

### Task 6: R2 key layout and the legacy installation sweep

**Files:**
- Modify: `backend/worker/src/archive.ts:1-75`
- Modify: `backend/worker/src/index.ts:66-83`
- Test: `backend/worker/test/index.test.ts`

**Interfaces:**
- Consumes: `hasExplicitDeviceHash` from Task 4, `payload.device_hash` from Task 4.
- Produces:
  - `archiveToR2(bucket: R2Bucket, payload: TelemetryPayload, hasExplicitDeviceHash: boolean): Promise<void>`
  - `sweepLegacyInstallation(bucket: R2Bucket, instanceHash: string): Promise<void>`

- [ ] **Step 1: Write the failing tests**

`createFakeBucket` needs a `delete` spy — extend it in place:

```ts
function createFakeBucket(opts: { fail?: boolean; deleteFails?: boolean } = {}) {
  return {
    put: vi.fn(async () => {
      if (opts.fail) {
        throw new Error("R2 unavailable");
      }
      return {} as R2Object;
    }),
    delete: vi.fn(async () => {
      if (opts.deleteFails) {
        throw new Error("R2 delete unavailable");
      }
    }),
  };
}
```

Then append, reusing `makeRequest`, `metricsPayload`, `installationPayload`, `DEVICE` and `HASH` from Task 4:

```ts
const LEGACY_INSTALL_KEY = `installations/install_${HASH.slice(0, 12)}.json`;

describe("R2 key layout (#395)", () => {
  it("keeps the legacy layout for a payload without device_hash", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(makeRequest(installationPayload()), makeEnv(bucket));
    expect(bucket.put.mock.calls[0][0]).toBe(LEGACY_INSTALL_KEY);
  });

  it("adds the device component when device_hash is explicit", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(
      makeRequest({ ...installationPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );
    expect(bucket.put.mock.calls[0][0]).toBe(
      `installations/install_${HASH.slice(0, 12)}_${DEVICE.slice(0, 12)}.json`,
    );
  });

  it("separates two units of one instance in the metrics archive", async () => {
    const bucket = createFakeBucket();
    const env = makeEnv(bucket);
    await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      env,
    );
    await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: "d".repeat(64) }),
      env,
    );

    const [keyA, keyB] = bucket.put.mock.calls.map((c) => c[0] as string);
    expect(keyA).not.toBe(keyB);
  });

  it("sweeps the stale legacy installation object", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(
      makeRequest({ ...installationPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );
    expect(bucket.delete).toHaveBeenCalledWith(LEGACY_INSTALL_KEY);
  });

  it("does not sweep for a legacy payload", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(makeRequest(installationPayload()), makeEnv(bucket));
    expect(bucket.delete).not.toHaveBeenCalled();
  });

  it("does not sweep for a metrics payload", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );
    expect(bucket.delete).not.toHaveBeenCalled();
  });

  it("still returns 202 when the sweep fails", async () => {
    const bucket = createFakeBucket({ deleteFails: true });
    const res = await worker.fetch(
      makeRequest({ ...installationPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );
    expect(res.status).toBe(202);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend/worker && npx vitest run`
Expected: FAIL — the device-component and sweep cases fail; the two legacy cases already pass.

- [ ] **Step 3: Implement the key layout and the sweep**

In `backend/worker/src/archive.ts`, update the header comment's file layout block to show both forms, then:

```ts
/**
 * Object-name suffix. Legacy payloads (no explicit device_hash) keep the
 * historical instance-only form so their objects stay at the same keys.
 * Payloads carrying a device_hash gain the unit component, which is also what
 * stops two entries of one instance from colliding on the same second (#395).
 */
function hashSuffix(payload: TelemetryPayload, hasExplicitDeviceHash: boolean): string {
  const instance = shortHash(payload.instance_hash);
  return hasExplicitDeviceHash
    ? `${instance}_${shortHash(payload.device_hash)}`
    : instance;
}

export async function archiveToR2(
  bucket: R2Bucket,
  payload: TelemetryPayload,
  hasExplicitDeviceHash: boolean,
): Promise<void> {
  const body = JSON.stringify(payload);
  const key = buildKey(payload, hasExplicitDeviceHash);
  await bucket.put(key, body, {
    httpMetadata: { contentType: "application/json" },
    customMetadata: {
      instance_hash: payload.instance_hash,
      device_hash: payload.device_hash,
      type: payload.type,
    },
  });
}

/**
 * Delete the pre-#395 installation object for an instance.
 *
 * That key was a single overwritten current-state document. Once a client
 * sends a device_hash it writes to the new key and never touches the old one
 * again, which would leave a stale object double-counting in a scan of
 * `installations/`. Best-effort and idempotent: the archive write is the
 * contract, so a delete failure must not fail the request.
 */
export async function sweepLegacyInstallation(
  bucket: R2Bucket,
  instanceHash: string,
): Promise<void> {
  await bucket.delete(`installations/install_${shortHash(instanceHash)}.json`);
}
```

Change `buildKey(payload)` to `buildKey(payload, hasExplicitDeviceHash)` and replace every `hash` use in it with `const suffix = hashSuffix(payload, hasExplicitDeviceHash);`:

```ts
    case "installation":
      return `installations/install_${suffix}.json`;
    case "metrics": {
      const firstTime = (payload as MetricsPayload).points[0]?.time;
      const { year, month, day } = dateParts(firstTime);
      return `metrics/year=${year}/month=${month}/day=${day}/batch_${ts}_${suffix}.json`;
    }
    case "daily_stats": {
      const { year, month } = dateParts((payload as DailyStatsPayload).date);
      return `daily_stats/year=${year}/month=${month}/daily_${(payload as DailyStatsPayload).date}_${suffix}.json`;
    }
    case "snapshot": {
      const { year, month, day } = dateParts();
      return `snapshots/year=${year}/month=${month}/day=${day}/snap_${ts}_${suffix}.json`;
    }
```

- [ ] **Step 4: Wire it into the request handler**

In `backend/worker/src/index.ts`, extend the import, widen the destructure Task 4 narrowed, extend the archive call, and add the sweep after `markRateLimit`:

```ts
import { archiveToR2, sweepLegacyInstallation } from "./archive";
```

```ts
      const { payload, hasExplicitDeviceHash } = validate(body, instanceHashHeader);
```

```ts
      try {
        await archiveToR2(env.ARCHIVE, payload, hasExplicitDeviceHash);
      } catch (err) {
        console.error("R2 archive failed:", err);
        return new Response("R2 archive unavailable", { status: 502 });
      }
```

```ts
      // Retire the pre-#395 instance-keyed installation object, which this
      // client will never write to again. Best-effort, like markRateLimit.
      if (payload.type === "installation" && hasExplicitDeviceHash) {
        try {
          await sweepLegacyInstallation(env.ARCHIVE, payload.instance_hash);
        } catch (err) {
          console.warn("sweepLegacyInstallation failed:", err);
        }
      }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend/worker && npx vitest run`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/worker/src/archive.ts backend/worker/src/index.ts \
        backend/worker/test/index.test.ts
git commit -m "fix(worker): key R2 objects per unit and sweep the legacy installation key"
```

---

### Task 7: Expose `device_hash` in the fleet dashboard

**Files:**
- Modify: `backend/worker/src/index.ts:85-110`
- Test: `backend/worker/test/index.test.ts`

**Interfaces:**
- Consumes: `payload.device_hash` from Task 4.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the failing tests**

`makeEnv` currently calls `createFakeAE()` inline (`test/index.test.ts:40-45`), so the fake it builds is unreachable from a test. Add a sibling helper next to it rather than changing `makeEnv`, so no existing test is disturbed:

```ts
/** Like makeEnv, but hands back the AE fake so its writes can be asserted. */
function makeEnvWithAE(bucket: ReturnType<typeof createFakeBucket>) {
  const ae = createFakeAE();
  const env = {
    ARCHIVE: bucket as unknown as R2Bucket,
    AE: ae as unknown as AnalyticsEngineDataset,
  } satisfies Env;
  return { env, ae };
}
```

Then append:

```ts
describe("WAE fleet dashboard (#395)", () => {
  it("keeps instance_hash as the index and blob1", async () => {
    const { env, ae } = makeEnvWithAE(createFakeBucket());
    await worker.fetch(
      makeRequest({ ...installationPayload(), device_hash: DEVICE }),
      env,
    );
    const point = ae.writeDataPoint.mock.calls[0][0];
    expect(point.indexes).toEqual([HASH]);
    expect(point.blobs[0]).toBe(HASH);
  });

  it("appends device_hash after climate_zone without shifting blobs", async () => {
    const { env, ae } = makeEnvWithAE(createFakeBucket());
    await worker.fetch(
      makeRequest({ ...installationPayload(), device_hash: DEVICE }),
      env,
    );
    const point = ae.writeDataPoint.mock.calls[0][0];
    expect(point.blobs).toHaveLength(8);
    expect(point.blobs[1]).toBe("yutaki_s80");
    expect(point.blobs[7]).toBe(DEVICE);
  });

  it("falls back to instance_hash for a legacy payload", async () => {
    const { env, ae } = makeEnvWithAE(createFakeBucket());
    await worker.fetch(makeRequest(installationPayload()), env);
    const point = ae.writeDataPoint.mock.calls[0][0];
    expect(point.blobs[7]).toBe(HASH);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend/worker && npx vitest run`
Expected: FAIL — `point.blobs` has length 7 and `blobs[7]` is `undefined`.

- [ ] **Step 3: Append the blob**

In `backend/worker/src/index.ts`, add one entry at the **end** of the `blobs` array, after `d.climate_zone ?? ""`:

```ts
            blobs: [
              payload.instance_hash,
              d.profile,
              d.gateway_type,
              d.power_supply ?? "",
              d.integration_version ?? "",
              d.ha_version ?? "",
              d.climate_zone ?? "",
              // Appended, never inserted: WAE blobs are positional and the
              // Grafana dashboard is not versioned in this repo, so shifting
              // blob1-blob7 would silently break every existing query (#395).
              payload.device_hash,
            ],
```

Leave `indexes: [payload.instance_hash]` untouched — that is what keeps the historical series continuous.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend/worker && npx vitest run`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/worker/src/index.ts backend/worker/test/index.test.ts
git commit -m "feat(worker): expose device_hash as blob8 for per-unit fleet counts"
```

---

### Task 8: Documentation and changelog

**Files:**
- Modify: `docs/reference/telemetry.md`
- Modify: `docs/development/telemetry-dataset.md:16`, `:41-42`
- Modify: `AGENT.md` (Anonymous Telemetry section)
- Modify: `CHANGELOG.md` (`[Unreleased]`)

**Interfaces:**
- Consumes: the final behaviour from Tasks 1-7.
- Produces: nothing.

- [ ] **Step 1: Update the telemetry reference**

In `docs/reference/telemetry.md`, document that every payload carries two identities: `instance_hash` (SHA-256 of the HA instance id, one per household) and `device_hash` (SHA-256 of `f"{instance_id}:{entry.unique_id}"`, one per heat-pump unit). State that the rate limit is 1 request per 60s per `(device_hash, payload_type)`, and that a payload without `device_hash` falls back to the instance identity for backward compatibility.

- [ ] **Step 2: Update the dataset guide**

In `docs/development/telemetry-dataset.md`:

- Line 16, replace the installation key with both forms:

  ```
  installations/install_<instance12>_<device12>.json   (clients >= this release)
  installations/install_<instance12>.json              (legacy, swept on first new send)
  ```

- Lines 41-42, the fixture-building workflow matches snapshot files by filename hash prefix. Note that new objects carry `<instance12>_<device12>`, so a prefix match on `<instance12>` still finds every unit of a household, and appending `_<device12>` narrows it to one unit. Add the same note for `metrics/`.

- [ ] **Step 3: Update AGENT.md**

In the **Anonymous Telemetry** section, amend the anonymizer bullet to mention both hashes, and the backend bullet to say the rate limit and R2 keys are per unit while WAE keeps `instance_hash` as its index with `device_hash` appended as `blob8`.

- [ ] **Step 4: Add the changelog entry**

Under `[Unreleased]` in `CHANGELOG.md`, in `Fixed`:

```markdown
- Telemetry on installations with more than one Hitachi gateway: every config entry
  shared a single `instance_hash` derived from the Home Assistant instance, so the
  ingestion endpoint's rate limit (1 request per 60s per identity) rejected all but
  one flush per 5-minute cycle, permanently. Each entry now sends its own
  `device_hash`, derived from the gateway hardware identifier, so the rate limit,
  the R2 archive keys and the fleet dashboard address a heat-pump unit rather than a
  household. Two silent archive defects are fixed with it: installation payloads from
  different units no longer overwrite each other, and two entries flushing in the same
  second no longer collide on the same metrics object name. Failed sends now re-queue
  their buffered points instead of dropping them (bounded to 30 minutes), and every
  telemetry log line carries the config entry name, with rate-limit rejections raised
  from DEBUG to WARNING so the cause is visible. Single-gateway installations are
  unaffected and their fleet history is continuous (#395).
```

- [ ] **Step 5: Verify and commit**

Run: `make check`
Expected: PASS

```bash
git add docs/reference/telemetry.md docs/development/telemetry-dataset.md \
        AGENT.md CHANGELOG.md
git commit -m "docs: document per-unit telemetry identity"
```

---

## Deployment

The Worker is backward compatible, and an un-upgraded Worker tolerates the new client: each `validate*` function builds a fresh result object from known fields and never rejects unknown top-level keys, so a `device_hash` sent to an old Worker is dropped rather than rejected. Order is therefore free, but deploy the Worker first so the first upgraded client already benefits:

```bash
cd backend/worker && npx wrangler deploy
```

Then open the PR against `main`.

## Post-merge verification

- Confirm on the reporter's install (#395) that the `Telemetry flush: send returned failure` warnings stop, and that each entry name now appears in any remaining telemetry log line.
- Confirm in Grafana that existing panels still render (they read `blob1`-`blob7`, untouched), and that `count(distinct blob8)` exceeds `count(distinct index1)` once a multi-gateway install has upgraded.
- Confirm in R2 that `installations/` no longer holds a stale `install_<instance12>.json` for an upgraded instance.
