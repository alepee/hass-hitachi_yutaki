"""Setup-time binding of an entry to its heat pump unit (#476).

``_async_bind_unit`` is gateway-agnostic: the client locates the unit
(``async_bind_unit``) and the gateway's config provider says what identifies
it. These tests drive it with canned bindings; the HC-A(16/64)MB lookup itself
is covered in ``tests/api/modbus/hc_a_mb/test_client.py``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki import _async_bind_unit
from custom_components.hitachi_yutaki.api.base import UnitBinding, UnitBindingStatus
from custom_components.hitachi_yutaki.api.config_providers.atw_mbs_02 import (
    AtwMbs02ConfigProvider,
)
from custom_components.hitachi_yutaki.api.config_providers.hc_a_mb import (
    HcAMbConfigProvider,
)
from custom_components.hitachi_yutaki.const import (
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

PLACEHOLDERS = {"outdoor_cycle": "5", "indoor_address": "6"}


def _entry(hass: HomeAssistant, title: str = "PAC", **data) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data={
            "gateway_type": "modbus_hc_a_mb",
            CONF_MODBUS_HOST: DEFAULT_HOST,
            CONF_MODBUS_PORT: DEFAULT_PORT,
            **data,
        },
    )
    entry.add_to_hass(hass)
    return entry


def _client(binding: UnitBinding) -> MagicMock:
    client = MagicMock()
    client.async_bind_unit = AsyncMock(return_value=binding)
    client.connected = True
    client.close = AsyncMock()
    return client


async def _bind(hass, entry, binding, provider=None) -> MagicMock:
    client = _client(binding)
    await _async_bind_unit(hass, entry, client, provider or HcAMbConfigProvider())
    return client


def _issue(hass: HomeAssistant, kind: str, entry: MockConfigEntry):
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{kind}_{entry.entry_id}")


@pytest.mark.asyncio
async def test_bound_unit_is_persisted(hass: HomeAssistant) -> None:
    """What the client found is written to the entry."""
    entry = _entry(hass, unit_id=2, outdoor_cycle=5, indoor_address=6)
    updates = {"unit_id": 1, "outdoor_cycle": 5, "indoor_address": 6}

    await _bind(hass, entry, UnitBinding(UnitBindingStatus.BOUND, updates))

    assert entry.data["unit_id"] == 1


@pytest.mark.asyncio
async def test_missing_unit_defers_setup_and_raises_an_issue(
    hass: HomeAssistant,
) -> None:
    """A missing unit: retry later, tell the user, release the connection."""
    entry = _entry(hass, unit_id=0, outdoor_cycle=5, indoor_address=6)
    missing = UnitBinding(UnitBindingStatus.MISSING, placeholders=PLACEHOLDERS)
    client = _client(missing)

    with pytest.raises(ConfigEntryNotReady):
        await _async_bind_unit(hass, entry, client, HcAMbConfigProvider())

    issue = _issue(hass, "unit_not_found", entry)
    assert issue.translation_placeholders == {"name": "PAC", **PLACEHOLDERS}
    client.close.assert_awaited_once()

    # The unit is back: the issue clears.
    await _bind(hass, entry, UnitBinding(UnitBindingStatus.BOUND))
    assert _issue(hass, "unit_not_found", entry) is None


@pytest.mark.asyncio
async def test_settling_gateway_defers_setup_without_an_issue(
    hass: HomeAssistant,
) -> None:
    """A gateway still enumerating its units is retried, not reported."""
    entry = _entry(hass, unit_id=0)

    with pytest.raises(ConfigEntryNotReady):
        await _bind(hass, entry, UnitBinding(UnitBindingStatus.SETTLING))

    assert not ir.async_get(hass).issues


@pytest.mark.asyncio
async def test_unverified_binding_keeps_the_entry(hass: HomeAssistant) -> None:
    """An inconclusive lookup leaves the stored configuration untouched."""
    entry = _entry(hass, unit_id=2)

    await _bind(hass, entry, UnitBinding(UnitBindingStatus.UNVERIFIED))

    assert dict(entry.data)["unit_id"] == 2
    assert not ir.async_get(hass).issues


@pytest.mark.asyncio
async def test_two_entries_on_one_unit_raise_an_issue(hass: HomeAssistant) -> None:
    """A second entry resolving to a unit already bound is not set up."""
    _entry(hass, "Yutampo", unit_id=2, outdoor_cycle=5, indoor_address=6)
    entry = _entry(hass, "Copy", unit_id=2, outdoor_cycle=5)
    updates = {"unit_id": 2, "outdoor_cycle": 5, "indoor_address": 6}
    bound = UnitBinding(UnitBindingStatus.BOUND, updates, PLACEHOLDERS)

    with pytest.raises(ConfigEntryNotReady):
        await _bind(hass, entry, bound)

    issue = _issue(hass, "unit_duplicate", entry)
    assert issue.translation_placeholders["other"] == "Yutampo"
    assert "indoor_address" not in entry.data


@pytest.mark.asyncio
async def test_single_unit_gateway_has_no_duplicate_check(
    hass: HomeAssistant,
) -> None:
    """Without a unit identity, two entries on one gateway are not compared."""
    _entry(hass, "First", gateway_type="modbus_atw_mbs_02")
    entry = _entry(hass, "Second", gateway_type="modbus_atw_mbs_02")

    await _bind(
        hass, entry, UnitBinding(UnitBindingStatus.BOUND), AtwMbs02ConfigProvider()
    )

    assert not ir.async_get(hass).issues
