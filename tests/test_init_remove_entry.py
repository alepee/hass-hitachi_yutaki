"""Tests for async_remove_entry cleanup of per-entry persistent artefacts."""

from __future__ import annotations

from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki import async_remove_entry
from custom_components.hitachi_yutaki.adapters.derived_metrics import (
    REFRIGERANT_STORE_VERSION,
)
from custom_components.hitachi_yutaki.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.storage import Store


def _make_entry(entry_id: str = "test_entry_id") -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Hitachi Heat Pump",
        data={"name": "Hitachi Heat Pump"},
        entry_id=entry_id,
    )


def _store_key(entry_id: str) -> str:
    """Return the refrigerant Store key for an entry."""
    return f"{DOMAIN}_refrigerant_{entry_id}"


def _create_per_entry_issues(hass: HomeAssistant, entry_id: str) -> list[str]:
    """Create the four per-entry repair issues and return their ids."""
    issue_ids = [
        f"missing_config_{entry_id}",
        f"enable_energy_cost_{entry_id}",
        f"enable_telemetry_{entry_id}",
        f"refrigerant_charge_alert_{entry_id}",
    ]
    for issue_id in issue_ids:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="connection_error",
        )
    return issue_ids


async def test_store_deleted(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """The refrigerant Store is removed when the entry is removed."""
    entry = _make_entry()
    store = Store(hass, REFRIGERANT_STORE_VERSION, _store_key(entry.entry_id))
    await store.async_save({"baseline": 42})

    assert _store_key(entry.entry_id) in hass_storage

    await async_remove_entry(hass, entry)

    assert _store_key(entry.entry_id) not in hass_storage


async def test_no_store_is_noop(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Removing an entry with no Store raises no exception."""
    entry = _make_entry()

    await async_remove_entry(hass, entry)

    assert _store_key(entry.entry_id) not in hass_storage


async def test_per_entry_issues_deleted(hass: HomeAssistant) -> None:
    """The four per-entry repair issues are deleted on entry removal."""
    entry = _make_entry()
    issue_ids = _create_per_entry_issues(hass, entry.entry_id)

    registry = ir.async_get(hass)
    for issue_id in issue_ids:
        assert registry.async_get_issue(DOMAIN, issue_id) is not None

    await async_remove_entry(hass, entry)

    for issue_id in issue_ids:
        assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_global_issues_preserved_when_another_entry_remains(
    hass: HomeAssistant,
) -> None:
    """Domain-global issues survive while another entry still exists."""
    entry = _make_entry("first_entry")
    other = _make_entry("second_entry")
    other.add_to_hass(hass)

    ir.async_create_issue(
        hass,
        DOMAIN,
        "connection_error",
        is_fixable=False,
        severity=IssueSeverity.ERROR,
        translation_key="connection_error",
    )

    await async_remove_entry(hass, entry)

    registry = ir.async_get(hass)
    assert registry.async_get_issue(DOMAIN, "connection_error") is not None


async def test_global_issues_swept_on_last_removal(hass: HomeAssistant) -> None:
    """Domain-global issues are swept when the last entry is removed."""
    entry = _make_entry()

    global_ids = ("connection_error", "desync_warning", "initializing_warning")
    for issue_id in global_ids:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="connection_error",
        )

    await async_remove_entry(hass, entry)

    registry = ir.async_get(hass)
    for issue_id in global_ids:
        assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_end_to_end_removal(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Removing a NOT_LOADED entry via HA cleans up store and issues.

    The entry is the last one of the domain, so the removal must also sweep
    the domain-global issues through the real ``async_remove`` path.
    """
    entry = _make_entry()
    entry.add_to_hass(hass)

    store = Store(hass, REFRIGERANT_STORE_VERSION, _store_key(entry.entry_id))
    await store.async_save({"baseline": 42})
    assert _store_key(entry.entry_id) in hass_storage

    issue_id = f"missing_config_{entry.entry_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="connection_error",
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        "connection_error",
        is_fixable=False,
        severity=IssueSeverity.ERROR,
        translation_key="connection_error",
    )

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert _store_key(entry.entry_id) not in hass_storage
    registry = ir.async_get(hass)
    assert registry.async_get_issue(DOMAIN, issue_id) is None
    assert registry.async_get_issue(DOMAIN, "connection_error") is None
