"""Tests for the refrigerant "circuit serviced" repair flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki.const import DOMAIN
from custom_components.hitachi_yutaki.repairs import (
    RefrigerantServicedRepairFlow,
    async_create_fix_flow,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir


def _make_entry(*, entry_id: str = "test_entry_id") -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Hitachi Heat Pump",
        data={
            "name": "Hitachi Heat Pump",
            "modbus_host": "192.168.0.4",
            "modbus_port": 502,
            "modbus_device_id": 1,
            "gateway_type": "modbus_atw_mbs_02",
            "profile": "yutaki_s",
            "power_supply": "single",
        },
        options={},
        entry_id=entry_id,
        version=2,
        minor_version=2,
    )


async def _init_flow(
    hass: HomeAssistant, issue_id: str
) -> RefrigerantServicedRepairFlow:
    """Create and initialize a RefrigerantServicedRepairFlow with context."""
    flow = RefrigerantServicedRepairFlow()
    flow.hass = hass
    flow.issue_id = issue_id
    flow.handler = DOMAIN
    flow.init_data = {"issue_id": issue_id}
    return flow


class TestRefrigerantServicedRepairFlow:
    """Tests for the RefrigerantServicedRepairFlow."""

    @pytest.mark.asyncio
    async def test_init_redirects_to_confirm(self, hass: HomeAssistant) -> None:
        """Verify async_step_init redirects to the confirm form."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        flow = await _init_flow(hass, f"refrigerant_charge_alert_{entry.entry_id}")
        result = await flow.async_step_init(
            {"issue_id": "refrigerant_charge_alert_test"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

    @pytest.mark.asyncio
    async def test_confirm_shows_form(self, hass: HomeAssistant) -> None:
        """Verify the confirm step presents a plain confirmation form."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        flow = await _init_flow(hass, f"refrigerant_charge_alert_{entry.entry_id}")
        result = await flow.async_step_confirm()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

    @pytest.mark.asyncio
    async def test_confirm_aborts_if_entry_not_found(self, hass: HomeAssistant) -> None:
        """Verify the flow aborts when the config entry no longer exists."""
        flow = await _init_flow(hass, "refrigerant_charge_alert_nonexistent_entry")
        result = await flow.async_step_confirm()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "entry_not_found"

    @pytest.mark.asyncio
    async def test_confirm_forwards_stale_placeholders(
        self, hass: HomeAssistant
    ) -> None:
        """Verify the stale issue's placeholders reach the confirm form."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        issue_id = f"refrigerant_charge_alert_{entry.entry_id}"
        placeholders = {"last_valid_day": "2026-03-28", "days_since_valid_data": "117"}
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="refrigerant_charge_alert_stale",
            translation_placeholders=placeholders,
        )

        flow = await _init_flow(hass, issue_id)
        result = await flow.async_step_confirm()

        assert result["type"] is FlowResultType.FORM
        assert result["description_placeholders"] == placeholders

    @pytest.mark.asyncio
    async def test_confirm_resets_baseline(self, hass: HomeAssistant) -> None:
        """Verify confirming resets the detector baseline and ends the flow."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        coordinator = AsyncMock()
        entry.runtime_data = coordinator

        flow = await _init_flow(hass, f"refrigerant_charge_alert_{entry.entry_id}")
        result = await flow.async_step_confirm({})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        coordinator.async_reset_refrigerant_baseline.assert_awaited_once()


class TestAsyncCreateFixFlowDispatch:
    """The factory dispatches refrigerant issues to the serviced flow."""

    @pytest.mark.asyncio
    async def test_dispatches_refrigerant_flow(self, hass: HomeAssistant) -> None:
        """Verify refrigerant_charge_alert_* issues get the serviced flow."""
        flow = await async_create_fix_flow(hass, "refrigerant_charge_alert_xyz", None)
        assert isinstance(flow, RefrigerantServicedRepairFlow)
