# Gateway Sync Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gracefully handle the ATW-MBS-02 gateway getting stuck in "initializing" state (register 1094 = 2) for extended periods (issue #254).

**Architecture:** Add a `ReadResult` enum to signal gateway readiness from the Modbus adapter layer. The coordinator reacts by applying exponential backoff on polling interval, raising `UpdateFailed` to mark entities unavailable, and throttling log spam. The system_state preflight also gets proper deserialization.

**Tech Stack:** Python 3.12, Home Assistant DataUpdateCoordinator, pymodbus, pytest

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `custom_components/hitachi_yutaki/api/base.py` | Abstract API client + `ReadResult` enum | Modify |
| `custom_components/hitachi_yutaki/api/modbus/__init__.py` | Modbus client: preflight, retries, connection | Modify |
| `custom_components/hitachi_yutaki/coordinator.py` | HA coordinator: polling, data flow, backoff | Modify |
| `tests/api/modbus/test_client.py` | Modbus client unit tests | Modify |
| `tests/test_coordinator.py` | Coordinator unit tests | Create |

---

### Task 1: Add `ReadResult` enum to `api/base.py`

**Files:**
- Modify: `custom_components/hitachi_yutaki/api/base.py:1-4,62-64`

- [ ] **Step 1: Add `ReadResult` enum and update `read_values` signature**

```python
# At the top of api/base.py, add the import and enum BEFORE the class definition:

"""Base classes for Hitachi API."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from custom_components.hitachi_yutaki.const import CIRCUIT_IDS, CIRCUIT_MODES


class ReadResult(Enum):
    """Result of a read_values operation."""

    SUCCESS = "success"
    GATEWAY_NOT_READY = "gateway_not_ready"
```

Then change the abstract method signature on line 62-64:

```python
    @abstractmethod
    async def read_values(self, keys_to_read: list[str]) -> ReadResult:
        """Fetch data from the heat pump for the given keys."""
```

- [ ] **Step 2: Run linter to verify**

Run: `make check`
Expected: PASS (the enum is valid Python, signature change is compatible)

- [ ] **Step 3: Commit**

```bash
git add custom_components/hitachi_yutaki/api/base.py
git commit -m "refactor: add ReadResult enum to API base class"
```

---

### Task 2: Fix `system_state` deserialization in preflight

**Files:**
- Modify: `custom_components/hitachi_yutaki/api/modbus/__init__.py:315-366`
- Test: `tests/api/modbus/test_client.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/api/modbus/test_client.py`:

```python
from custom_components.hitachi_yutaki.api.base import ReadResult
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
)


def _make_preflight_api_client(mock_hass, mock_client):
    """Create a ModbusApiClient with register map for preflight tests."""
    with patch.object(ModbusApiClient, "__init__", lambda x, *args, **kwargs: None):
        api = ModbusApiClient.__new__(ModbusApiClient)
        api._hass = mock_hass
        api._client = mock_client
        api._slave = 1
        api._data = {}
        api._register_map = AtwMbs02RegisterMap()
        api._gateway_not_ready_since = None
        api._gateway_not_ready_last_log = 0.0
        return api


@pytest.mark.asyncio
async def test_read_values_deserializes_system_state_on_state_0(mock_hass, mock_client):
    """Test system_state is deserialized to 'synchronized' when state is 0."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.read_holding_registers.return_value = _make_modbus_result(0)

    result = await api.read_values(["system_state"])

    assert result == ReadResult.SUCCESS
    assert api._data["system_state"] == "synchronized"


@pytest.mark.asyncio
async def test_read_values_deserializes_system_state_on_state_2(mock_hass, mock_client):
    """Test system_state is deserialized to 'initializing' when state is 2."""
    api = _make_preflight_api_client(mock_hass, mock_client)

    # First call: preflight returns state 2. Second call would be register read (not reached).
    mock_client.read_holding_registers.return_value = _make_modbus_result(2)

    result = await api.read_values(["system_state"])

    assert result == ReadResult.GATEWAY_NOT_READY
    assert api._data["system_state"] == "initializing"


@pytest.mark.asyncio
async def test_read_values_deserializes_system_state_on_state_1(mock_hass, mock_client):
    """Test system_state is deserialized to 'desynchronized' when state is 1."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.read_holding_registers.return_value = _make_modbus_result(1)

    result = await api.read_values(["system_state"])

    assert result == ReadResult.GATEWAY_NOT_READY
    assert api._data["system_state"] == "desynchronized"


@pytest.mark.asyncio
async def test_read_values_returns_success_on_normal_read(mock_hass, mock_client):
    """Test read_values returns SUCCESS when gateway is synchronized."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.read_holding_registers.return_value = _make_modbus_result(0)

    result = await api.read_values(["system_state"])

    assert result == ReadResult.SUCCESS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL - `read_values` returns `None` not `ReadResult`, and `_data["system_state"]` is `int` not `str`

- [ ] **Step 3: Implement deserialization fix and return `ReadResult`**

In `custom_components/hitachi_yutaki/api/modbus/__init__.py`, update `read_values()`:

Add import at top of file:
```python
from ..base import ReadResult
```

Replace lines 315-384 (the `read_values` method signature and body through the success return):

```python
    async def read_values(self, keys: list[str]) -> ReadResult:
        """Fetch data from the heat pump for the given keys."""
        retry_count = 0
        max_read_retries = 1  # Only retry once after reconnection

        while retry_count <= max_read_retries:
            try:
                device_param = get_pymodbus_device_param()
                all_regs = self._register_map.all_registers

                # Build a map of registers to read for this update
                registers_to_read = {
                    key: all_regs[key] for key in keys if key in all_regs
                }

                # Always perform a preflight check
                system_state_def = all_regs["system_state"]
                preflight_result = await self._hass.async_add_executor_job(
                    lambda param=device_param, addr=system_state_def.address: (
                        self._client.read_holding_registers(
                            address=addr,
                            count=1,
                            **{param: self._slave},
                        )
                    )
                )
                if preflight_result.isError():
                    raise ModbusException("Preflight check failed")

                raw_state = preflight_result.registers[0]

                # Always store deserialized value for entity consumption
                if system_state_def.deserializer:
                    self._data["system_state"] = system_state_def.deserializer(raw_state)
                else:
                    self._data["system_state"] = raw_state

                # Report system state issues and skip further reads
                for (
                    issue_state,
                    issue_key,
                ) in self._register_map.system_state_issues.items():
                    if raw_state == issue_state:
                        ir.async_create_issue(
                            self._hass,
                            DOMAIN,
                            issue_key,
                            is_fixable=False,
                            severity=ir.IssueSeverity.WARNING,
                            translation_key=issue_key,
                        )

                        _LOGGER.warning(
                            "Gateway is not ready (state: %s), skipping further reads for this cycle.",
                            raw_state,
                        )
                        return ReadResult.GATEWAY_NOT_READY
                    else:
                        ir.async_delete_issue(self._hass, DOMAIN, issue_key)

                for name, definition in registers_to_read.items():
                    value = await self._read_register(definition, device_param)
                    if value is None and definition.fallback:
                        value = await self._read_register(
                            definition.fallback, device_param
                        )
                    if value is not None:
                        self._data[name] = value
                    else:
                        _LOGGER.debug(
                            "Error reading register %s at %s", name, definition.address
                        )

                # If we got here, read was successful
                return ReadResult.SUCCESS

            except (ModbusException, ConnectionError, OSError) as exc:
                if retry_count < max_read_retries:
                    _LOGGER.warning(
                        "Communication error during read_values: %s. Attempting reconnection...",
                        exc,
                    )

                    # Force connection reset
                    with contextlib.suppress(Exception):
                        await self._hass.async_add_executor_job(self._client.close)

                    # Attempt immediate reconnection
                    if await self._ensure_connection():
                        _LOGGER.warning(
                            "Reconnection successful after read error, retrying read operation"
                        )
                        retry_count += 1
                        continue
                    else:
                        _LOGGER.error("Reconnection failed, data read aborted")
                        raise

                # Max retries reached or reconnection failed
                _LOGGER.warning("Modbus error during read_values: %s", exc)
                raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/hitachi_yutaki/api/modbus/__init__.py tests/api/modbus/test_client.py
git commit -m "fix: deserialize system_state in preflight and return ReadResult"
```

---

### Task 3: Add log throttling to `read_values()`

**Files:**
- Modify: `custom_components/hitachi_yutaki/api/modbus/__init__.py:44-56,362-366`
- Test: `tests/api/modbus/test_client.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/api/modbus/test_client.py`:

```python
import time


@pytest.mark.asyncio
async def test_read_values_throttles_gateway_not_ready_logs(
    mock_hass, mock_client, caplog
):
    """Test that repeated gateway-not-ready warnings are throttled."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.read_holding_registers.return_value = _make_modbus_result(2)

    # First call should log
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        await api.read_values(["system_state"])
        first_warnings = [r for r in caplog.records if "not ready" in r.message]
        assert len(first_warnings) == 1

    # Second call immediately after should NOT log
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        await api.read_values(["system_state"])
        second_warnings = [r for r in caplog.records if "not ready" in r.message]
        assert len(second_warnings) == 0


@pytest.mark.asyncio
async def test_read_values_logs_recovery_after_gateway_not_ready(
    mock_hass, mock_client, caplog
):
    """Test that recovery is logged when gateway returns to normal."""
    api = _make_preflight_api_client(mock_hass, mock_client)

    # First: gateway not ready
    mock_client.read_holding_registers.return_value = _make_modbus_result(2)
    await api.read_values(["system_state"])

    # Then: gateway recovers
    mock_client.read_holding_registers.return_value = _make_modbus_result(0)
    with caplog.at_level(logging.INFO):
        caplog.clear()
        await api.read_values(["system_state"])
        recovery_logs = [r for r in caplog.records if "recovered" in r.message.lower()]
        assert len(recovery_logs) == 1


@pytest.mark.asyncio
async def test_read_values_resets_throttle_state_on_recovery(mock_hass, mock_client):
    """Test that throttle state is reset after recovery."""
    api = _make_preflight_api_client(mock_hass, mock_client)

    # Not ready
    mock_client.read_holding_registers.return_value = _make_modbus_result(2)
    await api.read_values(["system_state"])
    assert api._gateway_not_ready_since is not None

    # Recovered
    mock_client.read_holding_registers.return_value = _make_modbus_result(0)
    await api.read_values(["system_state"])
    assert api._gateway_not_ready_since is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL - `_gateway_not_ready_since` attribute doesn't exist, log throttling not implemented

- [ ] **Step 3: Implement log throttling**

Add import at top of `api/modbus/__init__.py`:
```python
import time
```

Add to `ModbusApiClient.__init__()` after line 55 (`self._max_retries = 3`):
```python
        self._gateway_not_ready_since: float | None = None
        self._gateway_not_ready_last_log: float = 0.0
```

In `read_values()`, replace the gateway-not-ready logging block. Where you currently have:

```python
                        _LOGGER.warning(
                            "Gateway is not ready (state: %s), skipping further reads for this cycle.",
                            raw_state,
                        )
                        return ReadResult.GATEWAY_NOT_READY
```

Replace with:

```python
                        now = time.monotonic()
                        if self._gateway_not_ready_since is None:
                            # First detection
                            self._gateway_not_ready_since = now
                            self._gateway_not_ready_last_log = now
                            _LOGGER.warning(
                                "Gateway is not ready (state: %s), skipping further reads for this cycle.",
                                raw_state,
                            )
                        elif now - self._gateway_not_ready_last_log >= 300:
                            # Periodic reminder every 5 minutes
                            elapsed = int(now - self._gateway_not_ready_since)
                            self._gateway_not_ready_last_log = now
                            _LOGGER.warning(
                                "Gateway still not ready (state: %s), ongoing for %d minutes.",
                                raw_state,
                                elapsed // 60,
                            )
                        return ReadResult.GATEWAY_NOT_READY
```

After the `system_state_issues` loop (just before the register read loop), add recovery detection:

```python
                # Gateway is ready - check if we're recovering from a not-ready state
                if self._gateway_not_ready_since is not None:
                    elapsed = int(time.monotonic() - self._gateway_not_ready_since)
                    _LOGGER.info(
                        "Gateway recovered after %d minutes.",
                        elapsed // 60,
                    )
                    self._gateway_not_ready_since = None
                    self._gateway_not_ready_last_log = 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/hitachi_yutaki/api/modbus/__init__.py tests/api/modbus/test_client.py
git commit -m "fix: throttle gateway-not-ready log spam to every 5 minutes"
```

---

### Task 4: Coordinator adaptive backoff and `UpdateFailed`

**Files:**
- Modify: `custom_components/hitachi_yutaki/coordinator.py:1-111`
- Create: `tests/test_coordinator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_coordinator.py`:

```python
"""Tests for HitachiYutakiDataCoordinator gateway sync resilience."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hitachi_yutaki.api.base import ReadResult
from custom_components.hitachi_yutaki.coordinator import HitachiYutakiDataCoordinator
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    return hass


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    client = MagicMock()
    client.connected = True
    client.read_values = AsyncMock(return_value=ReadResult.SUCCESS)
    client.read_value = AsyncMock(return_value=None)
    client.register_map.base_keys = ["system_state"]
    client.is_defrosting = False
    return client


@pytest.fixture
def mock_profile():
    """Create a mock heat pump profile."""
    profile = MagicMock()
    profile.extra_register_keys = []
    return profile


@pytest.fixture
def coordinator(mock_hass, mock_api_client, mock_profile):
    """Create a coordinator instance."""
    entry = MagicMock()
    entry.data = {CONF_SCAN_INTERVAL: 5}

    with patch(
        "custom_components.hitachi_yutaki.coordinator.ir"
    ):
        coord = HitachiYutakiDataCoordinator(
            mock_hass, entry, mock_api_client, mock_profile
        )
    return coord


@pytest.mark.asyncio
async def test_coordinator_raises_update_failed_on_gateway_not_ready(
    coordinator, mock_api_client
):
    """Test that UpdateFailed is raised when gateway is not ready."""
    mock_api_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY

    with patch(
        "custom_components.hitachi_yutaki.coordinator.ir"
    ), pytest.raises(UpdateFailed, match="Gateway is not ready"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_backoff_increases_interval(coordinator, mock_api_client):
    """Test that polling interval increases on repeated gateway-not-ready."""
    mock_api_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY
    normal = coordinator._normal_interval

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        # First failure: 2x
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        assert coordinator.update_interval == normal * 2

        # Second failure: 4x
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        assert coordinator.update_interval == normal * 4

        # Third failure: 8x
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        assert coordinator.update_interval == normal * 8


@pytest.mark.asyncio
async def test_coordinator_backoff_capped_at_300s(coordinator, mock_api_client):
    """Test that backoff interval is capped at 300 seconds."""
    mock_api_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        for _ in range(10):
            with pytest.raises(UpdateFailed):
                await coordinator._async_update_data()

    assert coordinator.update_interval <= timedelta(seconds=300)


@pytest.mark.asyncio
async def test_coordinator_restores_interval_on_recovery(coordinator, mock_api_client):
    """Test that interval is restored when gateway recovers."""
    normal = coordinator._normal_interval

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        # Trigger backoff
        mock_api_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY
        for _ in range(3):
            with pytest.raises(UpdateFailed):
                await coordinator._async_update_data()
        assert coordinator.update_interval > normal

        # Recovery
        mock_api_client.read_values.return_value = ReadResult.SUCCESS
        await coordinator._async_update_data()
        assert coordinator.update_interval == normal
        assert coordinator._gateway_not_ready_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL - coordinator doesn't have `_normal_interval`, doesn't handle `ReadResult`

- [ ] **Step 3: Implement coordinator backoff**

Replace the full content of `custom_components/hitachi_yutaki/coordinator.py`:

```python
"""DataUpdateCoordinator for Hitachi Yutaki integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import HitachiApiClient
from .api.base import ReadResult
from .const import (
    CIRCUIT_IDS,
    CIRCUIT_MODES,
    DOMAIN,
)
from .domain.services.defrost_guard import DefrostGuard
from .profiles import HitachiHeatPumpProfile

_LOGGER = logging.getLogger(__name__)

_MAX_BACKOFF = timedelta(seconds=300)


class HitachiYutakiDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Hitachi heat pump data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api_client: HitachiApiClient,
        profile: HitachiHeatPumpProfile,
    ) -> None:
        """Initialize."""
        self.api_client = api_client
        self.profile = profile
        self.entities: list[Any] = []
        self.defrost_guard = DefrostGuard()
        self._normal_interval = timedelta(seconds=entry.data[CONF_SCAN_INTERVAL])
        self._gateway_not_ready_count: int = 0

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self._normal_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Hitachi Yutaki."""
        try:
            if not self.api_client.connected:
                await self.api_client.connect()

            # Build full list of keys and fetch all data
            keys_to_read = (
                self.api_client.register_map.base_keys
                + self.profile.extra_register_keys
            )

            _LOGGER.debug("Reading %d keys from gateway", len(keys_to_read))
            result = await self.api_client.read_values(keys_to_read)

            if result == ReadResult.GATEWAY_NOT_READY:
                self._gateway_not_ready_count += 1
                backoff = min(
                    self._normal_interval * (2 ** self._gateway_not_ready_count),
                    _MAX_BACKOFF,
                )
                self.update_interval = backoff
                raise UpdateFailed(
                    "Gateway is not ready (initializing or desynchronized)"
                )

            # Gateway is ready - restore normal interval if needed
            if self._gateway_not_ready_count > 0:
                _LOGGER.info(
                    "Gateway recovered, restoring normal polling interval (%ss).",
                    self._normal_interval.total_seconds(),
                )
                self._gateway_not_ready_count = 0
                self.update_interval = self._normal_interval

            data: dict[str, Any] = {"is_available": True}

            # Populate data from the client
            for key in keys_to_read:
                data[key] = await self.api_client.read_value(key)

            self.system_config = data.get("system_config", 0)

            # Update defrost guard with fresh data
            water_inlet = data.get("water_inlet_temp")
            water_outlet = data.get("water_outlet_temp")
            delta_t = (
                (water_outlet - water_inlet)
                if water_inlet is not None and water_outlet is not None
                else None
            )
            self.defrost_guard.update(
                is_defrosting=self.api_client.is_defrosting,
                delta_t=delta_t,
            )

            # If we reach here, connection is successful, so delete any connection error issue
            ir.async_delete_issue(self.hass, DOMAIN, "connection_error")

            # Update timing sensors
            for entity in self.entities:
                if hasattr(entity, "async_update_timing"):
                    await entity.async_update_timing()

            return data

        except UpdateFailed:
            raise

        except Exception as exc:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "connection_error",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="connection_error",
            )
            _LOGGER.warning("Error communicating with Hitachi Yutaki gateway: %s", exc)
            raise UpdateFailed("Failed to communicate with device") from exc

    def has_circuit(self, circuit_id: CIRCUIT_IDS, mode: CIRCUIT_MODES) -> bool:
        """Return True if circuit is configured in system_config."""
        return self.api_client.has_circuit(circuit_id, mode)

    def has_dhw(self) -> bool:
        """Return True if DHW is configured in system_config."""
        return self.api_client.has_dhw

    def has_pool(self) -> bool:
        """Return True if pool heating is configured in system_config."""
        return self.api_client.has_pool
```

Note the `except UpdateFailed: raise` block before the general `except Exception`. This is needed because `UpdateFailed` inherits from `Exception`, and the general handler would otherwise catch our intentional `UpdateFailed` from the backoff path and wrap it in a second `UpdateFailed`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/hitachi_yutaki/coordinator.py tests/test_coordinator.py
git commit -m "fix: add adaptive backoff and UpdateFailed on gateway not ready"
```

---

### Task 5: Final verification

**Files:**
- All modified files from Tasks 1-4

- [ ] **Step 1: Run full test suite**

Run: `make test`
Expected: All tests PASS

- [ ] **Step 2: Run linter**

Run: `make check`
Expected: All checks PASS

- [ ] **Step 3: Manual review of behavior**

Verify the expected behavior for the issue #254 scenario (gateway stuck at state 2 for ~58 min):

1. **Log output**: 1 WARNING at detection, then reminders every 5 min (~12 total instead of ~685)
2. **Polling interval**: 5s -> 10s -> 20s -> 40s -> 80s -> 160s -> 300s (capped) — ~25 polls instead of ~700
3. **Entity state**: `last_update_success = False` -> entities show "unavailable"
4. **system_state sensor**: shows "initializing" (string, not int `2`)
5. **Recovery**: interval restored, INFO log "Gateway recovered", entities become available again

- [ ] **Step 4: Commit final state if any fixups were needed**

```bash
git add -A
git commit -m "fix: gateway sync resilience for extended initializing state (#254)"
```
