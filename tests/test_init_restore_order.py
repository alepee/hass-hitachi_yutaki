"""Regression test for #432: energy counters are restored BEFORE the first poll.

The first refresh publishes ``coordinator.data`` for the entities created later
in ``async_setup_entry``; nothing re-injects a value restored afterwards. With
the restore placed after the refresh, ``power_consumption`` (TOTAL_INCREASING)
published 0.0 for one poll after every restart and HA statistics re-added the
lifetime total as new consumption.
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
    DEFAULT_DEVICE_ID,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_POWER_SUPPLY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

RESTORED_ENERGY_KWH = 1234.567
RESTORED_THERMAL_KWH = 4321.5


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        version=2,
        minor_version=4,
        domain=DOMAIN,
        title=DEFAULT_NAME,
        unique_id=f"{DOMAIN}_TESTRESTORE",
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
        },
        options={CONF_TELEMETRY_LEVEL: "off"},
    )


@pytest.mark.asyncio
async def test_energy_counters_restored_before_first_refresh(
    hass: HomeAssistant,
) -> None:
    """The first published data already carries the restored counters."""
    entry = _entry()
    entry.add_to_hass(hass)
    calls: list[str] = []

    async def fake_restore_energy(hass_, entry_, coordinator) -> None:
        calls.append("restore_energy")
        coordinator.derived_metrics.restore_accumulated_energy(RESTORED_ENERGY_KWH)

    async def fake_restore_thermal(hass_, entry_, coordinator) -> None:
        calls.append("restore_thermal")
        coordinator.derived_metrics.restore_thermal_energy(
            "thermal_energy_heating_total", RESTORED_THERMAL_KWH
        )

    async def fake_first_refresh(coordinator) -> bool:
        # Stand-in for a successful first poll: run the derived metrics on a
        # minimal register set and publish the result, as the coordinator does.
        calls.append("first_refresh")
        data = {"is_available": True, "compressor_current": 0.0}
        coordinator.derived_metrics.update(data)
        coordinator.async_set_updated_data(data)
        return True

    with (
        patch(
            "custom_components.hitachi_yutaki._async_first_refresh_tolerating_gateway_not_ready",
            side_effect=fake_first_refresh,
        ),
        patch(
            "custom_components.hitachi_yutaki._async_restore_thermal_energy",
            side_effect=fake_restore_thermal,
        ),
        patch(
            "custom_components.hitachi_yutaki._async_restore_energy_state",
            side_effect=fake_restore_energy,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        assert await async_setup_entry(hass, entry) is True

    assert calls.index("restore_thermal") < calls.index("first_refresh")
    assert calls.index("restore_energy") < calls.index("first_refresh")

    coordinator = entry.runtime_data
    # What the entities will read on creation: the restored totals, not 0.0.
    assert coordinator.data["electrical_energy_consumed"] == RESTORED_ENERGY_KWH
    assert coordinator.data["thermal_energy_heating_total"] == RESTORED_THERMAL_KWH
