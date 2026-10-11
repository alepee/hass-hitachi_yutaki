"""Setup-time wiring of the fleet ping and its one-time notice (#468)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.hitachi_yutaki.const import CONF_FLEET_PING, DOMAIN
from custom_components.hitachi_yutaki.telemetry.fleet_ping import DATA_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .test_init_telemetry_identity import _make_entry, _setup

_REGISTER = "custom_components.hitachi_yutaki.async_register_fleet_ping"


def _notice(hass: HomeAssistant, entry_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"fleet_ping_notice_{entry_id}")


@pytest.mark.asyncio
async def test_default_enrols_and_shows_notice(hass: HomeAssistant) -> None:
    """Telemetry off, no choice yet: the ping runs and the user is told."""
    entry = _make_entry(title="PAC", unique_id=f"{DOMAIN}_HW1_1")

    with patch(_REGISTER, AsyncMock()) as register:
        await _setup(hass, entry)

    register.assert_awaited_once()
    assert register.await_args.args[1] == entry.entry_id
    assert _notice(hass, entry.entry_id) is not None


@pytest.mark.asyncio
async def test_opted_out_is_not_enrolled(hass: HomeAssistant) -> None:
    """An explicit opt-out keeps the entry out of the ping, without notice."""
    entry = _make_entry(title="PAC", unique_id=f"{DOMAIN}_HW1_1")
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_FLEET_PING: False}
    )

    with patch(_REGISTER, AsyncMock()) as register:
        await _setup(hass, entry)

    register.assert_not_awaited()
    assert _notice(hass, entry.entry_id) is None


@pytest.mark.asyncio
async def test_telemetry_on_implies_ping_without_notice(hass: HomeAssistant) -> None:
    """Telemetry ON enrols the entry even if the ping was turned off."""
    entry = _make_entry(title="PAC", unique_id=f"{DOMAIN}_HW1_1", telemetry="on")
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_FLEET_PING: False}
    )

    with patch(_REGISTER, AsyncMock()) as register:
        await _setup(hass, entry)

    register.assert_awaited_once()
    assert _notice(hass, entry.entry_id) is None


@pytest.mark.asyncio
async def test_unload_unregisters(hass: HomeAssistant) -> None:
    """Unloading the only entry stops the instance's pinger."""
    entry = _make_entry(title="PAC", unique_id=f"{DOMAIN}_HW1_1")
    await _setup(hass, entry)
    assert DATA_KEY in hass.data

    # Run only the unload callbacks that are plain callables (the coordinator
    # also registers a coroutine shutdown, irrelevant here).
    for unsub in entry._on_unload or []:
        if getattr(unsub, "__name__", "") == "<lambda>":
            unsub()
    assert DATA_KEY not in hass.data
