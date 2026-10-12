"""Tests for capability handling during setup and device removal (#404).

Setup only continues on a fresh first refresh, so devices (gated on the live
capabilities in ``async_setup_entry``) and entities (gated on the same live
capabilities through their ``condition``) are always built from the same read.
COP services seeded from the persisted ``system_config`` (#308) are only
re-initialised when the live capabilities disagree with it. A circuit, DHW or
pool device the unit no longer declares can be removed from the UI.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki import (
    _should_reinit_cop_services,
    async_remove_config_entry_device,
    async_setup_entry,
)
from custom_components.hitachi_yutaki.api.base import ReadResult
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
)
from custom_components.hitachi_yutaki.const import (
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    CONF_MODBUS_DEVICE_ID,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_TELEMETRY_LEVEL,
    DEFAULT_DEVICE_ID,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_POWER_SUPPLY,
    DEFAULT_SCAN_INTERVAL,
    DEVICE_CIRCUIT_1,
    DEVICE_CONTROL_UNIT,
    DEVICE_DHW,
    DEVICE_POOL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

_ATW_REGISTERS = AtwMbs02RegisterMap()


def _caps(
    *,
    cooling: bool = False,
    dhw: bool = False,
    pool: bool = False,
) -> dict[str, bool]:
    return {"cooling": cooling, "dhw": dhw, "pool": pool}


def _full_capability_system_config() -> int:
    """Compose an ATW-MBS-02 system_config with dhw + pool + circuit2 + cooling."""
    masks = _ATW_REGISTERS.masks_circuit
    return (
        masks[(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING)]
        | masks[(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING)]
        | masks[(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING)]
        | masks[(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING)]
        | _ATW_REGISTERS.mask_dhw
        | _ATW_REGISTERS.mask_pool
    )


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        version=2,
        minor_version=4,
        domain=DOMAIN,
        title=DEFAULT_NAME,
        unique_id=f"{DOMAIN}_TESTHW1234",
        data={
            "gateway_type": "modbus_atw_mbs_02",
            "gateway_variant": "gen2",
            "name": DEFAULT_NAME,
            CONF_MODBUS_HOST: DEFAULT_HOST,
            CONF_MODBUS_PORT: DEFAULT_PORT,
            CONF_MODBUS_DEVICE_ID: DEFAULT_DEVICE_ID,
            "scan_interval": DEFAULT_SCAN_INTERVAL,
            "profile": "yutaki_s",
            "power_supply": DEFAULT_POWER_SUPPLY,
            "system_config": _full_capability_system_config(),
        },
        options={CONF_TELEMETRY_LEVEL: "off"},
    )


# --- COP-service mismatch re-init guard ----------------------------------


def test_reinit_when_live_disagrees_with_persisted():
    """Live capabilities disagreeing with persisted ones re-init COP services."""
    assert (
        _should_reinit_cop_services(
            live=_caps(cooling=True, dhw=True), persisted=_caps()
        )
        is True
    )


def test_no_reinit_when_live_matches_persisted():
    """Live capabilities matching persisted ones need no re-init."""
    caps = _caps(cooling=True, dhw=True, pool=True)

    assert _should_reinit_cop_services(live=caps, persisted=dict(caps)) is False


# --- Setup deferral (#404) -------------------------------------------------


@pytest.mark.asyncio
async def test_setup_entry_gateway_not_ready_defers_setup(
    hass: HomeAssistant,
) -> None:
    """A gateway still initializing defers setup and registers no device.

    Before #404, setup continued on empty register data: devices were
    registered from the persisted capabilities while the capability-gated
    entities were all dropped, leaving devices with no entities until a reload.
    """
    entry = _entry()
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    with (
        patch(
            "custom_components.hitachi_yutaki.api.modbus.ModbusApiClient.connect",
            AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.hitachi_yutaki.api.modbus.ModbusApiClient.read_values",
            AsyncMock(return_value=ReadResult.GATEWAY_NOT_READY),
        ),
        patch(
            "custom_components.hitachi_yutaki.api.modbus.ModbusApiClient.async_get_unique_id",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.hitachi_yutaki._async_restore_thermal_energy",
            AsyncMock(),
        ),
        patch(
            "custom_components.hitachi_yutaki._async_restore_energy_state",
            AsyncMock(),
        ),
        pytest.raises(ConfigEntryNotReady, match="not ready"),
    ):
        await async_setup_entry(hass, entry)

    device_registry = dr.async_get(hass)
    assert dr.async_entries_for_config_entry(device_registry, entry.entry_id) == []


# --- Device removal (#404) -------------------------------------------------


def _loaded_entry(
    hass: HomeAssistant, *, dhw: bool, pool: bool, circuit1: bool = True
) -> MockConfigEntry:
    entry = _entry()
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    coordinator = MagicMock()
    coordinator.has_circuit = MagicMock(
        side_effect=lambda circuit_id, mode: (
            circuit1
            and circuit_id == CIRCUIT_PRIMARY_ID
            and mode == CIRCUIT_MODE_HEATING
        )
    )
    coordinator.has_dhw = MagicMock(return_value=dhw)
    coordinator.has_pool = MagicMock(return_value=pool)
    entry.runtime_data = coordinator
    return entry


def _device(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> dr.DeviceEntry:
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{key}")},
    )


@pytest.mark.asyncio
async def test_remove_undeclared_device_is_allowed(hass: HomeAssistant) -> None:
    """A pool device the unit does not declare (phantom) can be removed."""
    entry = _loaded_entry(hass, dhw=True, pool=False)

    assert await async_remove_config_entry_device(
        hass, entry, _device(hass, entry, DEVICE_POOL)
    )


@pytest.mark.asyncio
async def test_remove_declared_device_is_refused(hass: HomeAssistant) -> None:
    """Devices the unit declares cannot be removed."""
    entry = _loaded_entry(hass, dhw=True, pool=False)

    assert not await async_remove_config_entry_device(
        hass, entry, _device(hass, entry, DEVICE_DHW)
    )
    assert not await async_remove_config_entry_device(
        hass, entry, _device(hass, entry, DEVICE_CIRCUIT_1)
    )


@pytest.mark.asyncio
async def test_remove_core_device_is_refused(hass: HomeAssistant) -> None:
    """The control unit always exists and cannot be removed."""
    entry = _loaded_entry(hass, dhw=False, pool=False)

    assert not await async_remove_config_entry_device(
        hass, entry, _device(hass, entry, DEVICE_CONTROL_UNIT)
    )


@pytest.mark.asyncio
async def test_remove_refused_when_entry_not_loaded(hass: HomeAssistant) -> None:
    """Without a loaded entry the capabilities are unknown: refuse removal."""
    entry = _entry()
    entry.add_to_hass(hass)

    assert not await async_remove_config_entry_device(
        hass, entry, _device(hass, entry, DEVICE_POOL)
    )
