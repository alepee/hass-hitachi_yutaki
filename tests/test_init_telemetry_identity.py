"""Setup-time wiring of the per-unit telemetry identity (#395).

``hash_device_id`` is unit-tested in isolation, but the defect behind #395 was
in the *wiring*: the hash the coordinator actually sends was derived from the
Home Assistant instance, so every config entry of one household shared it. A
future refactor back to, say, ``entry.entry_id`` would reproduce the bug with a
green suite unless the derivation is pinned here.

The back-fill fallback is covered too: when the Modbus hardware read fails,
every entry of a multi-unit gateway must still get a distinct ``unique_id``,
because the back-fill only runs while it is ``None`` and therefore never
self-heals.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki import async_setup_entry
from custom_components.hitachi_yutaki.const import (
    CONF_MODBUS_DEVICE_ID,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_TELEMETRY_LEVEL,
    CONF_UNIT_ID,
    DEFAULT_DEVICE_ID,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_POWER_SUPPLY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from custom_components.hitachi_yutaki.telemetry.anonymizer import (
    hash_device_id,
    hash_instance_id,
)
from custom_components.hitachi_yutaki.telemetry.http_client import HttpTelemetryClient
from homeassistant.core import HomeAssistant
from homeassistant.helpers.instance_id import async_get as async_get_instance_id


def _make_entry(
    *,
    title: str,
    unique_id: str | None,
    unit_id: int = 1,
    telemetry: str = "off",
) -> MockConfigEntry:
    """Build a minimal HC-A(16/64)MB entry with telemetry off (no network)."""
    return MockConfigEntry(
        version=2,
        minor_version=4,
        domain=DOMAIN,
        title=title,
        unique_id=unique_id,
        data={
            "gateway_type": "modbus_hc_a_mb",
            "name": DEFAULT_NAME,
            CONF_MODBUS_HOST: DEFAULT_HOST,
            CONF_MODBUS_PORT: DEFAULT_PORT,
            CONF_MODBUS_DEVICE_ID: DEFAULT_DEVICE_ID,
            CONF_UNIT_ID: unit_id,
            "scan_interval": DEFAULT_SCAN_INTERVAL,
            "profile": "yutaki_s",
            "power_supply": DEFAULT_POWER_SUPPLY,
        },
        options={CONF_TELEMETRY_LEVEL: telemetry},
    )


async def _setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    *,
    connects: bool = True,
    hardware_id: str | None = None,
):
    """Run async_setup_entry with I/O and platforms stubbed out."""
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.hitachi_yutaki._async_first_refresh_tolerating_gateway_not_ready",
            AsyncMock(return_value=False),
        ),
        patch(
            "custom_components.hitachi_yutaki.api.modbus.ModbusApiClient.connect",
            AsyncMock(return_value=connects),
        ),
        patch(
            "custom_components.hitachi_yutaki.api.modbus.ModbusApiClient.async_get_unique_id",
            AsyncMock(return_value=hardware_id),
        ),
        patch(
            "custom_components.hitachi_yutaki.api.modbus.ModbusApiClient.close",
            AsyncMock(),
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.hitachi_yutaki._async_restore_thermal_energy",
            AsyncMock(),
        ),
        patch(
            "custom_components.hitachi_yutaki._async_restore_energy_state",
            AsyncMock(),
        ),
    ):
        assert await async_setup_entry(hass, entry) is True

    return entry.runtime_data


@pytest.mark.asyncio
async def test_device_hash_is_derived_from_the_entry_unique_id(
    hass: HomeAssistant,
) -> None:
    """The hash the coordinator sends must come from entry.unique_id."""
    entry = _make_entry(title="PAC 1", unique_id=f"{DOMAIN}_TESTHW1234_1")

    coordinator = await _setup(hass, entry)

    instance_id = await async_get_instance_id(hass)
    meta = coordinator._telemetry_meta
    assert meta["device_hash"] == hash_device_id(instance_id, entry.unique_id)
    assert meta["instance_hash"] == hash_instance_id(instance_id)
    assert meta["device_hash"] != meta["instance_hash"]


@pytest.mark.asyncio
async def test_two_entries_of_one_instance_get_distinct_device_hashes(
    hass: HomeAssistant,
) -> None:
    """The whole point of #395: one identity per heat-pump unit."""
    first = await _setup(
        hass, _make_entry(title="PAC 1", unique_id=f"{DOMAIN}_TESTHW1234_1", unit_id=1)
    )
    second = await _setup(
        hass, _make_entry(title="PAC 2", unique_id=f"{DOMAIN}_TESTHW1234_2", unit_id=2)
    )

    assert (
        first._telemetry_meta["instance_hash"]
        == second._telemetry_meta["instance_hash"]
    )
    assert first._telemetry_meta["device_hash"] != second._telemetry_meta["device_hash"]


@pytest.mark.asyncio
async def test_backfill_fallback_distinguishes_units_of_one_gateway(
    hass: HomeAssistant,
) -> None:
    """No hardware id available: the IP fallback must still include the unit.

    Two legacy entries behind the same HC-A(16/64)MB gateway share host and
    Modbus device id, so without the unit id both would back-fill to the same
    unique_id and therefore to the same device_hash.
    """
    first_entry = _make_entry(title="PAC 1", unique_id=None, unit_id=1)
    second_entry = _make_entry(title="PAC 2", unique_id=None, unit_id=2)

    first = await _setup(hass, first_entry, connects=False)
    second = await _setup(hass, second_entry, connects=False)

    assert first_entry.unique_id == f"{DEFAULT_HOST}_{DEFAULT_DEVICE_ID}_1"
    assert second_entry.unique_id == f"{DEFAULT_HOST}_{DEFAULT_DEVICE_ID}_2"
    assert first._telemetry_meta["device_hash"] != second._telemetry_meta["device_hash"]


@pytest.mark.asyncio
async def test_backfill_from_hardware_id_distinguishes_units(
    hass: HomeAssistant,
) -> None:
    """Hardware read succeeds: the unit id must still be part of the identity.

    Two legacy entries of one multi-unit HC-A(16/64)MB gateway read the *same*
    hardware identifier, since it identifies the gateway and not the unit
    behind it. Without the unit id suffix both back-fill to one unique_id and
    therefore to one device_hash, which is #395 again.
    """
    first_entry = _make_entry(title="PAC 1", unique_id=None, unit_id=1)
    second_entry = _make_entry(title="PAC 2", unique_id=None, unit_id=2)

    first = await _setup(hass, first_entry, hardware_id="TESTHW1234")
    second = await _setup(hass, second_entry, hardware_id="TESTHW1234")

    assert first_entry.unique_id == f"{DOMAIN}_TESTHW1234_1"
    assert second_entry.unique_id == f"{DOMAIN}_TESTHW1234_2"
    assert first._telemetry_meta["device_hash"] != second._telemetry_meta["device_hash"]


@pytest.mark.asyncio
async def test_setup_refuses_an_entry_left_without_a_unique_id(
    hass: HomeAssistant,
) -> None:
    """The guard exists so a None never gets hashed as the string "None".

    Every entry lacking one would then share a single device_hash, silently.
    The back-fill above makes this unreachable in practice, which is exactly
    why it must be pinned: a refactor moving the derivation above the back-fill
    would reintroduce #395 with no test failing.
    """
    entry = _make_entry(title="PAC 1", unique_id=None)

    with (
        patch.object(
            hass.config_entries, "async_update_entry", return_value=True
        ),  # back-fill result discarded: entry.unique_id stays None
        pytest.raises(ValueError, match="unique_id"),
    ):
        await _setup(hass, entry, connects=False)


@pytest.mark.asyncio
async def test_telemetry_client_is_labelled_with_the_entry_title(
    hass: HomeAssistant,
) -> None:
    """Log lines must name the entry, which is what made #395 diagnosable."""
    entry = _make_entry(
        title="PAC salon", unique_id=f"{DOMAIN}_TESTHW1234_1", telemetry="on"
    )

    coordinator = await _setup(hass, entry)

    assert isinstance(coordinator.telemetry_client, HttpTelemetryClient)
    assert coordinator.telemetry_client._prefix == "[PAC salon] "
