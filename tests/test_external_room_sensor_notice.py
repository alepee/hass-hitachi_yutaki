"""The one-time room-regulation notice and its repair flow."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki.const import (
    CONF_EXTERNAL_ROOM_SENSOR_NOTICE,
    DOMAIN,
)
from custom_components.hitachi_yutaki.repairs import (
    ExternalRoomSensorNoticeRepairFlow,
    async_create_fix_flow,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

pytestmark = pytest.mark.asyncio


def _make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Hitachi Heat Pump",
        data={"name": "Hitachi Heat Pump", "profile": "yutaki_s"},
        options={},
        entry_id="test_entry_id",
        version=2,
        minor_version=2,
    )


async def _repair_flow(
    hass: HomeAssistant, entry_id: str
) -> ExternalRoomSensorNoticeRepairFlow:
    issue_id = f"external_room_sensor_notice_{entry_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="external_room_sensor_notice",
    )
    flow = await async_create_fix_flow(hass, issue_id, None)
    assert isinstance(flow, ExternalRoomSensorNoticeRepairFlow)
    flow.hass = hass
    flow.issue_id = issue_id
    flow.handler = DOMAIN
    return flow


async def test_shows_the_notice(hass: HomeAssistant) -> None:
    """Init redirects to a confirm form that links to the documentation."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    flow = await _repair_flow(hass, entry.entry_id)

    result = await flow.async_step_init({"issue_id": flow.issue_id})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert "learn_more_url" in result["description_placeholders"]


async def test_confirming_records_the_read_and_clears(hass: HomeAssistant) -> None:
    """Confirming writes nothing to the unit, only remembers the notice was read."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    flow = await _repair_flow(hass, entry.entry_id)

    result = await flow.async_step_confirm({})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_EXTERNAL_ROOM_SENSOR_NOTICE] is True
    assert ir.async_get(hass).async_get_issue(DOMAIN, flow.issue_id) is None


async def test_orphaned_notice_aborts_and_self_deletes(hass: HomeAssistant) -> None:
    """A notice whose entry is gone removes itself (#409)."""
    flow = await _repair_flow(hass, "gone")

    result = await flow.async_step_confirm()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_found"
    assert ir.async_get(hass).async_get_issue(DOMAIN, flow.issue_id) is None
