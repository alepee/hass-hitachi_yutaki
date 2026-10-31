"""Tests for the "retry restoring the settings" repair flow (#511)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki.const import DOMAIN
from custom_components.hitachi_yutaki.repairs import (
    RetryKeptValuesRepairFlow,
    async_create_fix_flow,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir


def _make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Hitachi Heat Pump",
        data={"name": "Hitachi Heat Pump", "gateway_type": "modbus_atw_mbs_02"},
        entry_id="test_entry_id",
        version=2,
        minor_version=2,
    )


def _init_flow(hass: HomeAssistant, issue_id: str) -> RetryKeptValuesRepairFlow:
    flow = RetryKeptValuesRepairFlow()
    flow.hass = hass
    flow.issue_id = issue_id
    flow.handler = DOMAIN
    flow.init_data = {"issue_id": issue_id}
    return flow


@pytest.mark.asyncio
async def test_fix_flow_is_dispatched(hass: HomeAssistant) -> None:
    """The issue id routes to the retry flow."""
    flow = await async_create_fix_flow(hass, "kept_values_restore_failed_x", None)
    assert isinstance(flow, RetryKeptValuesRepairFlow)


@pytest.mark.asyncio
async def test_init_shows_the_confirm_form(hass: HomeAssistant) -> None:
    """Opening the issue asks for confirmation before retrying."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    flow = _init_flow(hass, f"kept_values_restore_failed_{entry.entry_id}")
    result = await flow.async_step_init()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"


@pytest.mark.asyncio
async def test_confirm_retries_the_restores(hass: HomeAssistant) -> None:
    """Confirming hands the retry to the coordinator."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    entry.runtime_data = MagicMock(async_retry_restores=AsyncMock())

    flow = _init_flow(hass, f"kept_values_restore_failed_{entry.entry_id}")
    result = await flow.async_step_confirm({})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry.runtime_data.async_retry_restores.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirm_aborts_if_entry_not_found(hass: HomeAssistant) -> None:
    """An orphaned issue is removed (#409)."""
    issue_id = "kept_values_restore_failed_nonexistent_entry"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="kept_values_restore_failed",
    )
    flow = _init_flow(hass, issue_id)
    result = await flow.async_step_confirm()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_found"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
