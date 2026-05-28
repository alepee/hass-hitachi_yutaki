"""Tests for persisting system_config (capability flags) into entry.data.

See issue #308: COP services / device capabilities must be initialisable at
setup time *before* any first refresh, so that a reload during the gateway's
H-LINK init window does not drop cooling / DHW / pool COP services for the
session.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hitachi_yutaki.api.base import ReadResult
from custom_components.hitachi_yutaki.coordinator import HitachiYutakiDataCoordinator
from custom_components.hitachi_yutaki.telemetry import (
    NoopTelemetryClient,
    TelemetryCollector,
    TelemetryLevel,
)
from homeassistant.const import CONF_SCAN_INTERVAL

_BASE_KEYS = ["system_config", "system_state"]


def _make_coordinator(initial_entry_data: dict, system_config_value: int):
    """Build a coordinator wired with read_value returning system_config_value."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    # Close the one-time telemetry coroutine immediately so we don't get
    # "coroutine was never awaited" warnings during the test.
    def _close_coro(coro):
        coro.close()

    hass.async_create_task = MagicMock(side_effect=_close_coro)

    api_client = MagicMock()
    api_client.connected = True
    api_client.read_values = AsyncMock(return_value=ReadResult.SUCCESS)
    api_client.is_defrosting = False
    api_client.is_compressor_running = False
    api_client.register_map.base_keys = list(_BASE_KEYS)

    async def _read_value(key: str):
        if key == "system_config":
            return system_config_value
        return None

    api_client.read_value = AsyncMock(side_effect=_read_value)

    profile = MagicMock()
    profile.extra_register_keys = []

    entry = MagicMock()
    entry.data = dict(initial_entry_data)
    entry.data.setdefault(CONF_SCAN_INTERVAL, 5)

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        coord = HitachiYutakiDataCoordinator(hass, entry, api_client, profile)

    coord.telemetry_collector = TelemetryCollector(level=TelemetryLevel.OFF)
    coord.telemetry_client = NoopTelemetryClient()
    coord._telemetry_meta = {
        "instance_hash": "test",
        "profile": "test",
        "gateway_type": "test",
        "ha_version": "test",
        "integration_version": "test",
        "power_supply": "single",
    }
    return coord, hass, entry


@pytest.mark.asyncio
async def test_coordinator_persists_system_config_on_first_successful_refresh():
    """First time we see a non-zero system_config, persist it in entry.data."""
    coord, hass, entry = _make_coordinator({}, system_config_value=0x1234)

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coord._async_update_data()

    hass.config_entries.async_update_entry.assert_called_once()
    args, kwargs = hass.config_entries.async_update_entry.call_args
    assert kwargs["data"]["system_config"] == 0x1234


@pytest.mark.asyncio
async def test_coordinator_does_not_write_when_system_config_unchanged():
    """No async_update_entry call when persisted value already matches live value."""
    coord, hass, entry = _make_coordinator(
        {"system_config": 0x1234}, system_config_value=0x1234
    )

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coord._async_update_data()

    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_coordinator_updates_persisted_value_when_changed():
    """When the live system_config differs from persisted, persist the new value."""
    coord, hass, entry = _make_coordinator(
        {"system_config": 0x1234}, system_config_value=0x5678
    )

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coord._async_update_data()

    hass.config_entries.async_update_entry.assert_called_once()
    args, kwargs = hass.config_entries.async_update_entry.call_args
    assert kwargs["data"]["system_config"] == 0x5678


@pytest.mark.asyncio
async def test_coordinator_does_not_persist_when_live_value_is_zero():
    """Guard against persisting a meaningless 0 when read returns None / 0."""
    coord, hass, entry = _make_coordinator({}, system_config_value=0)

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coord._async_update_data()

    hass.config_entries.async_update_entry.assert_not_called()


def test_coordinator_seeds_system_config_from_entry_data():
    """The coordinator exposes the persisted system_config before the first poll."""
    coord, _, _ = _make_coordinator({"system_config": 0x42}, system_config_value=0x42)
    assert coord.system_config == 0x42


def test_coordinator_defaults_system_config_to_zero():
    """Entries without persisted system_config (existing installs) default to 0."""
    coord, _, _ = _make_coordinator({}, system_config_value=0)
    assert coord.system_config == 0
