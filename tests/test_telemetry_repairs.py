"""Tests for telemetry repair flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki.const import (
    CONF_TELEMETRY_LEVEL,
    DOMAIN,
)
from custom_components.hitachi_yutaki.repairs import (
    EnableTelemetryRepairFlow,
    MissingConfigRepairFlow,
    async_create_fix_flow,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir


def _make_entry(
    *,
    options: dict | None = None,
    entry_id: str = "test_entry_id",
) -> MockConfigEntry:
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
        options=options or {},
        entry_id=entry_id,
        version=2,
        minor_version=2,
    )


async def _init_repair_flow(
    hass: HomeAssistant, issue_id: str
) -> EnableTelemetryRepairFlow:
    """Create and initialize an EnableTelemetryRepairFlow with proper context."""
    flow = EnableTelemetryRepairFlow()
    flow.hass = hass
    flow.issue_id = issue_id
    flow.handler = DOMAIN
    flow.init_data = {"issue_id": issue_id}
    return flow


class TestEnableTelemetryRepairFlow:
    """Tests for the EnableTelemetryRepairFlow."""

    @pytest.mark.asyncio
    async def test_init_redirects_to_confirm(self, hass: HomeAssistant) -> None:
        """Verify async_step_init redirects to confirm step showing the form."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        flow = await _init_repair_flow(hass, f"enable_telemetry_{entry.entry_id}")

        # init always redirects to confirm, even with data dict (like FlowManager passes)
        result = await flow.async_step_init({"issue_id": "enable_telemetry_test"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

    @pytest.mark.asyncio
    async def test_confirm_shows_form(self, hass: HomeAssistant) -> None:
        """Verify the confirm step presents the telemetry selection form."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        flow = await _init_repair_flow(hass, f"enable_telemetry_{entry.entry_id}")
        result = await flow.async_step_confirm()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

    @pytest.mark.asyncio
    async def test_confirm_saves_basic(self, hass: HomeAssistant) -> None:
        """Verify selecting 'basic' saves to entry.options and completes the flow."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        flow = await _init_repair_flow(hass, f"enable_telemetry_{entry.entry_id}")

        with patch.object(hass.config_entries, "async_reload"):
            result = await flow.async_step_confirm({CONF_TELEMETRY_LEVEL: "basic"})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_TELEMETRY_LEVEL] == "basic"

    @pytest.mark.asyncio
    async def test_confirm_saves_full(self, hass: HomeAssistant) -> None:
        """Verify selecting 'full' saves to entry.options and completes the flow."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        flow = await _init_repair_flow(hass, f"enable_telemetry_{entry.entry_id}")

        with patch.object(hass.config_entries, "async_reload"):
            result = await flow.async_step_confirm({CONF_TELEMETRY_LEVEL: "full"})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_TELEMETRY_LEVEL] == "full"

    @pytest.mark.asyncio
    async def test_confirm_saves_off(self, hass: HomeAssistant) -> None:
        """Verify selecting 'off' saves to entry.options and completes the flow."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        flow = await _init_repair_flow(hass, f"enable_telemetry_{entry.entry_id}")

        with patch.object(hass.config_entries, "async_reload"):
            result = await flow.async_step_confirm({CONF_TELEMETRY_LEVEL: "off"})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_TELEMETRY_LEVEL] == "off"

    @pytest.mark.asyncio
    async def test_confirm_default_is_off(self, hass: HomeAssistant) -> None:
        """Verify empty input defaults to 'off'."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        flow = await _init_repair_flow(hass, f"enable_telemetry_{entry.entry_id}")

        with patch.object(hass.config_entries, "async_reload"):
            result = await flow.async_step_confirm({})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_TELEMETRY_LEVEL] == "off"

    @pytest.mark.asyncio
    async def test_confirm_aborts_if_entry_not_found(
        self, hass: HomeAssistant
    ) -> None:
        """Verify the flow aborts when the config entry no longer exists."""
        flow = await _init_repair_flow(hass, "enable_telemetry_nonexistent_entry")
        result = await flow.async_step_confirm()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "entry_not_found"

    @pytest.mark.asyncio
    async def test_confirm_deletes_issue(self, hass: HomeAssistant) -> None:
        """Verify the repair issue is deleted after the flow completes."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        issue_id = f"enable_telemetry_{entry.entry_id}"

        # Create the issue first
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            issue_domain=DOMAIN,
            translation_key="enable_telemetry",
        )

        # Verify issue exists
        issue_registry = ir.async_get(hass)
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

        # Run the repair flow
        flow = await _init_repair_flow(hass, issue_id)

        with patch.object(hass.config_entries, "async_reload"):
            result = await flow.async_step_confirm({CONF_TELEMETRY_LEVEL: "basic"})

        assert result["type"] is FlowResultType.CREATE_ENTRY

        # Issue should be deleted
        issue_registry = ir.async_get(hass)
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    @pytest.mark.asyncio
    async def test_confirm_preserves_existing_options(
        self, hass: HomeAssistant
    ) -> None:
        """Verify the flow preserves other options already set on the entry."""
        entry = _make_entry(options={"some_other_option": "value"})
        entry.add_to_hass(hass)

        flow = await _init_repair_flow(hass, f"enable_telemetry_{entry.entry_id}")

        with patch.object(hass.config_entries, "async_reload"):
            result = await flow.async_step_confirm({CONF_TELEMETRY_LEVEL: "full"})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_TELEMETRY_LEVEL] == "full"
        assert entry.options["some_other_option"] == "value"


class TestTelemetryRepairIssueCreation:
    """Tests for repair issue creation logic."""

    @pytest.mark.asyncio
    async def test_repair_created_when_telemetry_not_in_options(
        self, hass: HomeAssistant
    ) -> None:
        """Verify a repair issue is created for entries without telemetry_level."""
        entry = _make_entry(options={})
        entry.add_to_hass(hass)

        # Simulate what __init__.py does
        if CONF_TELEMETRY_LEVEL not in entry.options:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"enable_telemetry_{entry.entry_id}",
                is_fixable=True,
                is_persistent=True,
                severity=ir.IssueSeverity.WARNING,
                issue_domain=DOMAIN,
                translation_key="enable_telemetry",
            )

        issue_registry = ir.async_get(hass)
        issue_id = f"enable_telemetry_{entry.entry_id}"
        issue = issue_registry.async_get_issue(DOMAIN, issue_id)
        assert issue is not None
        assert issue.is_fixable is True
        assert issue.is_persistent is True

    @pytest.mark.asyncio
    async def test_no_repair_when_telemetry_already_set(
        self, hass: HomeAssistant
    ) -> None:
        """Verify no repair issue is created when telemetry_level is already set."""
        entry = _make_entry(options={CONF_TELEMETRY_LEVEL: "off"})
        entry.add_to_hass(hass)

        # Simulate what __init__.py does — should NOT create issue
        if CONF_TELEMETRY_LEVEL not in entry.options:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"enable_telemetry_{entry.entry_id}",
                is_fixable=True,
                is_persistent=True,
                severity=ir.IssueSeverity.WARNING,
                issue_domain=DOMAIN,
                translation_key="enable_telemetry",
            )

        issue_registry = ir.async_get(hass)
        issue_id = f"enable_telemetry_{entry.entry_id}"
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


class TestAsyncCreateFixFlowDispatch:
    """Tests for the async_create_fix_flow factory dispatching."""

    @pytest.mark.asyncio
    async def test_dispatches_telemetry_flow(self, hass: HomeAssistant) -> None:
        """Verify enable_telemetry issues get EnableTelemetryRepairFlow."""
        flow = await async_create_fix_flow(
            hass, "enable_telemetry_some_entry_id", None
        )
        assert isinstance(flow, EnableTelemetryRepairFlow)

    @pytest.mark.asyncio
    async def test_dispatches_missing_config_flow(self, hass: HomeAssistant) -> None:
        """Verify missing_config issues get MissingConfigRepairFlow."""
        flow = await async_create_fix_flow(
            hass, "missing_config_some_entry_id", None
        )
        assert isinstance(flow, MissingConfigRepairFlow)

    @pytest.mark.asyncio
    async def test_unknown_issue_gets_missing_config_flow(
        self, hass: HomeAssistant
    ) -> None:
        """Verify unknown issue types fall back to MissingConfigRepairFlow."""
        flow = await async_create_fix_flow(hass, "unknown_issue_id", None)
        assert isinstance(flow, MissingConfigRepairFlow)
