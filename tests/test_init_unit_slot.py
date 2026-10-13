"""Setup-time binding of an HC-A(16/64)MB entry to its unit's slot (#476).

The gateway lists units sorted by H-LINK address and packs them from slot 0,
so a unit absent at enumeration shifts every unit above it. The entry stores
the unit's ``(Ou, Iu)`` pair and the slot is looked up at every setup.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki import _async_resolve_unit_slot
from custom_components.hitachi_yutaki.api.modbus.unit_table import parse_unit_table
from custom_components.hitachi_yutaki.const import (
    CONF_INDOOR_ADDRESS,
    CONF_MODBUS_DEVICE_ID,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_OUTDOOR_CYCLE,
    CONF_UNIT_ID,
    DEFAULT_DEVICE_ID,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

EMPTY = [0, 255, 255, 255]
# Dump A from #476: 2x Yutaki S, 2x Yutampo R32.
DUMP_A = [1, 0, 0, 0, 1, 1, 1, 1, 1, 5, 6, 2, 1, 7, 8, 3] + EMPTY * 12
# Yutaki S #1 (0, 0) absent at enumeration.
SHIFTED = [1, 1, 1, 0, 1, 5, 6, 1, 1, 7, 8, 2] + EMPTY * 13


def _entry(
    hass: HomeAssistant,
    *,
    unit_id: int,
    outdoor_cycle: int | None = None,
    indoor_address: int | None = None,
    gateway_type: str = "modbus_hc_a_mb",
    title: str = "PAC",
) -> MockConfigEntry:
    data = {
        "gateway_type": gateway_type,
        "name": DEFAULT_NAME,
        CONF_MODBUS_HOST: DEFAULT_HOST,
        CONF_MODBUS_PORT: DEFAULT_PORT,
        CONF_MODBUS_DEVICE_ID: DEFAULT_DEVICE_ID,
        CONF_UNIT_ID: unit_id,
    }
    if outdoor_cycle is not None:
        data[CONF_OUTDOOR_CYCLE] = outdoor_cycle
    if indoor_address is not None:
        data[CONF_INDOOR_ADDRESS] = indoor_address
    entry = MockConfigEntry(domain=DOMAIN, title=title, data=data)
    entry.add_to_hass(hass)
    return entry


@contextmanager
def _gateway(registers: list[int] | None):
    table = AsyncMock(
        return_value=None if registers is None else parse_unit_table(registers)
    )
    base = "custom_components.hitachi_yutaki.api.modbus.ModbusApiClient"
    with (
        patch(f"{base}.connect", AsyncMock(return_value=True)),
        patch(f"{base}.close", AsyncMock()),
        patch(f"{base}.async_read_unit_table", table),
    ):
        yield table


def _identity(entry: MockConfigEntry) -> tuple:
    return (
        entry.data[CONF_UNIT_ID],
        entry.data.get(CONF_OUTDOOR_CYCLE),
        entry.data.get(CONF_INDOOR_ADDRESS),
    )


@pytest.mark.asyncio
async def test_follows_a_unit_that_moved(hass: HomeAssistant) -> None:
    """The entry is rebound to the slot now holding its (Ou, Iu) pair."""
    entry = _entry(hass, unit_id=2, outdoor_cycle=5, indoor_address=6)

    with _gateway(SHIFTED):
        await _async_resolve_unit_slot(hass, entry)

    assert _identity(entry) == (1, 5, 6)


@pytest.mark.asyncio
async def test_absent_unit_defers_setup_and_raises_an_issue(
    hass: HomeAssistant,
) -> None:
    """An absent unit never reads whatever now occupies its old slot."""
    entry = _entry(hass, unit_id=0, outdoor_cycle=0, indoor_address=0)
    issue_id = f"unit_not_found_{entry.entry_id}"

    with _gateway(SHIFTED), pytest.raises(ConfigEntryNotReady):
        await _async_resolve_unit_slot(hass, entry)

    assert _identity(entry) == (0, 0, 0)
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

    # The unit is back: the issue clears.
    with _gateway(DUMP_A):
        await _async_resolve_unit_slot(hass, entry)
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.asyncio
async def test_settling_table_defers_setup_without_an_issue(
    hass: HomeAssistant,
) -> None:
    """A table mid re-enumeration is retried, not reported."""
    entry = _entry(hass, unit_id=0, outdoor_cycle=0, indoor_address=0)
    settling = [1, 1, 1, 0, 1, 0, 0, 255] + EMPTY * 14

    with _gateway(settling), pytest.raises(ConfigEntryNotReady):
        await _async_resolve_unit_slot(hass, entry)

    assert not ir.async_get(hass).issues


@pytest.mark.asyncio
async def test_legacy_entry_records_its_indoor_address(hass: HomeAssistant) -> None:
    """Entries created after #353 but before #476 self-heal Iu from their cycle."""
    entry = _entry(hass, unit_id=3, outdoor_cycle=7)

    with _gateway(DUMP_A):
        await _async_resolve_unit_slot(hass, entry)

    assert _identity(entry) == (3, 7, 8)


@pytest.mark.asyncio
async def test_pre_353_entry_adopts_its_slot(hass: HomeAssistant) -> None:
    """Entries with no identity at all take the one in their stored slot."""
    entry = _entry(hass, unit_id=2)

    with _gateway(DUMP_A):
        await _async_resolve_unit_slot(hass, entry)

    assert _identity(entry) == (2, 5, 6)


@pytest.mark.asyncio
async def test_pre_353_entry_on_an_empty_slot_is_left_alone(
    hass: HomeAssistant,
) -> None:
    """Nothing to compare against: keep the previous best-effort behaviour."""
    entry = _entry(hass, unit_id=6)

    with _gateway(DUMP_A):
        await _async_resolve_unit_slot(hass, entry)

    assert _identity(entry) == (6, None, None)
    assert not ir.async_get(hass).issues


@pytest.mark.asyncio
async def test_unreadable_table_keeps_the_stored_slot(hass: HomeAssistant) -> None:
    """An unreadable table is not fatal: the first refresh decides."""
    entry = _entry(hass, unit_id=1, outdoor_cycle=1, indoor_address=1)

    with _gateway(None):
        await _async_resolve_unit_slot(hass, entry)

    assert _identity(entry) == (1, 1, 1)


@pytest.mark.asyncio
async def test_two_entries_on_one_unit_raise_an_issue(hass: HomeAssistant) -> None:
    """A second entry resolving to a unit already bound is not set up."""
    _entry(hass, unit_id=1, outdoor_cycle=5, indoor_address=6, title="Yutampo")
    entry = _entry(hass, unit_id=2, outdoor_cycle=5, title="Copy")

    with _gateway(DUMP_A), pytest.raises(ConfigEntryNotReady):
        await _async_resolve_unit_slot(hass, entry)

    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"unit_duplicate_{entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_placeholders["other"] == "Yutampo"


@pytest.mark.asyncio
async def test_atw_mbs_02_entries_are_untouched(hass: HomeAssistant) -> None:
    """Single-unit gateways have no unit table."""
    entry = _entry(hass, unit_id=0, gateway_type="modbus_atw_mbs_02")

    with _gateway(DUMP_A) as table:
        await _async_resolve_unit_slot(hass, entry)

    table.assert_not_called()
