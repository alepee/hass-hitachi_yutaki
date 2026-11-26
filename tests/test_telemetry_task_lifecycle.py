"""Background telemetry work belongs to the config entry that started it.

A send still running when its entry unloads would otherwise carry on with the
old coordinator: retrying the installation payload with a client the user may
just have turned off, or flushing a buffer nobody owns anymore.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hitachi_yutaki import (
    TELEMETRY_FLUSH_INTERVAL,
    _schedule_telemetry_flush,
)
from custom_components.hitachi_yutaki.api.base import ReadResult
from custom_components.hitachi_yutaki.const import DOMAIN
from custom_components.hitachi_yutaki.coordinator import HitachiYutakiDataCoordinator
from custom_components.hitachi_yutaki.telemetry import (
    TelemetryCollector,
    TelemetryLevel,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant


def _api_client() -> MagicMock:
    client = MagicMock()
    client.connected = True
    client.read_values = AsyncMock(return_value=ReadResult.SUCCESS)
    client.async_verify_unit = AsyncMock(return_value=True)
    client.read_value = AsyncMock(return_value=None)
    client.base_keys = ["system_state"]
    client.is_defrosting = False
    client.is_compressor_running = False
    client.restore_failed = False
    client.restore_lost_values = AsyncMock()
    client.has_dhw = MagicMock(return_value=False)
    client.has_pool = MagicMock(return_value=False)
    client.has_circuit = MagicMock(return_value=False)
    return client


def _coordinator(
    hass: HomeAssistant, entry: MockConfigEntry
) -> HitachiYutakiDataCoordinator:
    profile = MagicMock()
    profile.extra_register_keys = []
    profile.max_circuits = 2
    profile.supports_secondary_compressor = False
    profile.supports_extended_compressor_sensors = False
    coordinator = HitachiYutakiDataCoordinator(hass, entry, _api_client(), profile)
    coordinator.telemetry_collector = TelemetryCollector(level=TelemetryLevel.ON)
    coordinator._telemetry_meta = {
        "instance_hash": "a" * 64,
        "device_hash": "b" * 64,
        "profile": "yutaki_s",
        "gateway_type": "modbus_atw_mbs_02",
        "ha_version": "2026.10.0",
        "integration_version": "2.5.0",
        "power_supply": "single",
    }
    return coordinator


@pytest.mark.asyncio
async def test_onetime_send_is_cancelled_when_the_entry_unloads(
    hass: HomeAssistant,
) -> None:
    """The installation send started by a poll does not outlive its entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_SCAN_INTERVAL: 5})
    entry.add_to_hass(hass)
    coordinator = _coordinator(hass, entry)

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _never_answers(_payload) -> bool:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return True

    client = MagicMock()
    client.send_installation = AsyncMock(side_effect=_never_answers)
    client.send_snapshot = AsyncMock(return_value=True)
    coordinator.telemetry_client = client

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_update_data()
    await asyncio.wait_for(started.wait(), 1)

    await entry._async_process_on_unload(hass)

    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_onetime_send_runs_one_at_a_time(hass: HomeAssistant) -> None:
    """A poll during a send in flight does not start a second one."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_SCAN_INTERVAL: 5})
    entry.add_to_hass(hass)
    coordinator = _coordinator(hass, entry)

    release = asyncio.Event()

    async def _slow(_payload) -> bool:
        await release.wait()
        return True

    client = MagicMock()
    client.send_installation = AsyncMock(side_effect=_slow)
    client.send_snapshot = AsyncMock(return_value=True)
    coordinator.telemetry_client = client

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_update_data()
        await asyncio.sleep(0)
        await coordinator._async_update_data()
    release.set()
    await hass.async_block_till_done()

    assert client.send_installation.await_count == 1
    assert coordinator._installation_info_sent


@pytest.mark.asyncio
async def test_flush_in_flight_is_cancelled_when_the_entry_unloads(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A periodic flush does not race the final unload flush."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_SCAN_INTERVAL: 5})
    entry.add_to_hass(hass)

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _never_answers() -> bool:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return True

    coordinator = MagicMock()
    coordinator.async_flush_telemetry = AsyncMock(side_effect=_never_answers)
    _schedule_telemetry_flush(hass, entry, coordinator)

    freezer.tick(TELEMETRY_FLUSH_INTERVAL)
    async_fire_time_changed(hass)
    await asyncio.wait_for(started.wait(), 1)

    await entry._async_process_on_unload(hass)

    assert cancelled.is_set()
