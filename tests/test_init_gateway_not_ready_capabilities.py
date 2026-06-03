"""Tests for capability resolution when first refresh is tolerated (#317).

Issue #317 (two linked HIGH-severity symptoms) -- when the first refresh is
tolerated through ``gateway_not_ready`` (#303/#307), ``api_client._data`` is
left EMPTY, so the LIVE ``coordinator.has_*()`` capabilities all return False.

Symptom 1: COP services seeded from the persisted ``system_config`` (#308) get
destroyed by the live-vs-persisted mismatch re-init.

Symptom 2: DHW/Pool/Circuit devices, gated on the LIVE ``has_*()``, are not
registered during setup.

These tests exercise ``_resolve_effective_capabilities`` -- the pure helper that
chooses LIVE flags when data is fresh and falls back to the persisted flags
when it is not -- and the mismatch-reinit guard ``_should_reinit_cop_services``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki import (
    _resolve_effective_capabilities,
    _should_reinit_cop_services,
    async_setup_entry,
)
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
    DEVICE_CIRCUIT_2,
    DEVICE_DHW,
    DEVICE_POOL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

_ATW_REGISTERS = AtwMbs02RegisterMap()


def _caps(
    *,
    circuit1: bool = False,
    circuit2: bool = False,
    cooling: bool = False,
    dhw: bool = False,
    pool: bool = False,
) -> dict[str, bool]:
    return {
        "circuit1": circuit1,
        "circuit2": circuit2,
        "cooling": cooling,
        "dhw": dhw,
        "pool": pool,
    }


# --- Symptom 2: device-gating capabilities -------------------------------


def test_fresh_data_uses_live_capabilities():
    """When data is fresh, LIVE capabilities are authoritative."""
    live = _caps(circuit1=True, dhw=True)
    persisted = _caps(circuit1=True, circuit2=True, cooling=True, dhw=True, pool=True)

    effective = _resolve_effective_capabilities(
        data_is_fresh=True, live=live, persisted=persisted
    )

    # Live wins entirely, persisted is ignored.
    assert effective == live


def test_stale_data_falls_back_to_persisted_capabilities():
    """Stale data: persisted flags drive device gating (#317 symptom 2)."""
    # Empty _data -> every live flag is False.
    live = _caps()
    persisted = _caps(circuit1=True, circuit2=True, cooling=True, dhw=True, pool=True)

    effective = _resolve_effective_capabilities(
        data_is_fresh=False, live=live, persisted=persisted
    )

    assert effective == persisted
    # The whole point: DHW / Pool / Circuit2 devices would be registered.
    assert effective["dhw"] is True
    assert effective["pool"] is True
    assert effective["circuit2"] is True
    assert effective["circuit1"] is True


def test_stale_data_heating_only_does_not_invent_capabilities():
    """Stale fallback must not over-register: heating-only stays heating-only."""
    live = _caps()
    persisted = _caps(circuit1=True)

    effective = _resolve_effective_capabilities(
        data_is_fresh=False, live=live, persisted=persisted
    )

    assert effective["circuit1"] is True
    assert effective["circuit2"] is False
    assert effective["cooling"] is False
    assert effective["dhw"] is False
    assert effective["pool"] is False


# --- Symptom 1: COP-service mismatch re-init guard -----------------------


def test_no_reinit_when_data_is_stale():
    """Stale data: never re-init COP services -> persisted #308 seeding survives."""
    # Live all-False, persisted full capability -> a naive mismatch check would
    # fire and DESTROY the COP services. The guard must prevent that.
    live = _caps()
    persisted = _caps(cooling=True, dhw=True, pool=True)

    assert (
        _should_reinit_cop_services(data_is_fresh=False, live=live, persisted=persisted)
        is False
    )


def test_reinit_when_fresh_and_live_disagrees_with_persisted():
    """Fresh data disagreeing with persisted must re-init (preserve old behaviour)."""
    live = _caps(cooling=True, dhw=True, pool=False)
    persisted = _caps(cooling=False, dhw=False, pool=False)

    assert (
        _should_reinit_cop_services(data_is_fresh=True, live=live, persisted=persisted)
        is True
    )


def test_no_reinit_when_fresh_and_live_matches_persisted():
    """Fresh data matching persisted needs no re-init (avoid redundant work)."""
    live = _caps(cooling=True, dhw=True, pool=True)
    persisted = _caps(cooling=True, dhw=True, pool=True)

    assert (
        _should_reinit_cop_services(data_is_fresh=True, live=live, persisted=persisted)
        is False
    )


# --- Integration: full async_setup_entry wiring (#317) -------------------


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


@pytest.mark.asyncio
async def test_setup_entry_tolerated_gateway_not_ready_registers_optional_devices(
    hass: HomeAssistant,
) -> None:
    """async_setup_entry wiring: tolerated gateway_not_ready + full persisted caps.

    Regression guard for #317. The first refresh is tolerated (returns False),
    so the real ModbusApiClient keeps an EMPTY ``_data`` and every live
    ``has_*()`` reads False. The persisted ``system_config`` declares a full
    reversible unit with DHW + pool + circuit 2. We assert:

      (b/symptom 2) the DHW, Pool and Circuit 2 devices are registered, driven
        by the persisted fallback rather than the empty live flags;
      (a/symptom 1) the COP services seeded from the persisted system_config
        survive -- they are NOT reset to the heating-only no-capability set.

    Pre-fix, the buggy path registered ZERO optional devices and re-initialised
    the COP services from the all-False live flags (heating only).
    """
    entry = MockConfigEntry(
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
            # Full reversible unit with DHW + pool + circuit 2, persisted by a
            # previous successful poll (#308).
            "system_config": _full_capability_system_config(),
        },
        # Telemetry OFF so the noop client is used (no network).
        options={CONF_TELEMETRY_LEVEL: "off"},
    )
    entry.add_to_hass(hass)

    with (
        # First refresh tolerates gateway_not_ready -> returns False and leaves
        # the real api_client's _data empty (live has_*() all False).
        patch(
            "custom_components.hitachi_yutaki._async_first_refresh_tolerating_gateway_not_ready",
            AsyncMock(return_value=False),
        ),
        # Skip platform setup and recorder-backed restore/rehydrate: this test
        # targets only the capability wiring, not entity platforms.
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
        result = await async_setup_entry(hass, entry)

    assert result is True

    coordinator = entry.runtime_data

    # Sanity: the first refresh left the live capabilities empty (the bug's
    # precondition). If this ever became True, the test would no longer exercise
    # the stale-data path.
    assert coordinator.has_dhw() is False
    assert coordinator.has_pool() is False

    # (b) Symptom 2: optional devices registered from the persisted fallback.
    device_registry = dr.async_get(hass)
    for device_key in (DEVICE_DHW, DEVICE_POOL, DEVICE_CIRCUIT_2):
        identifier = (DOMAIN, f"{entry.entry_id}_{device_key}")
        assert device_registry.async_get_device(identifiers={identifier}) is not None, (
            f"expected device {device_key} to be registered from persisted caps"
        )

    # (a) Symptom 1: COP services seeded from persisted system_config survive.
    cop_services = coordinator.derived_metrics._cop_services
    assert "cop_heating" in cop_services
    assert "cop_cooling" in cop_services
    assert "cop_dhw" in cop_services
    assert "cop_pool" in cop_services
