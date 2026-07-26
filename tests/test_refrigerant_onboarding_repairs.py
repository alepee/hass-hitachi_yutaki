"""Tests for the refrigerant-detection onboarding repair flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki.const import (
    CONF_REFRIGERANT_DETECTION,
    DOMAIN,
)
from custom_components.hitachi_yutaki.profiles import PROFILES
from custom_components.hitachi_yutaki.repairs import (
    EnableRefrigerantDetectionRepairFlow,
    MissingConfigRepairFlow,
    async_create_fix_flow,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir


def _make_entry(
    *,
    options: dict | None = None,
    profile: str = "yutaki_s",
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
            "profile": profile,
            "power_supply": "single",
        },
        options=options or {},
        entry_id=entry_id,
        version=2,
        minor_version=4,
    )


async def _init_repair_flow(
    hass: HomeAssistant, issue_id: str
) -> EnableRefrigerantDetectionRepairFlow:
    """Create and initialize a repair flow with proper context."""
    flow = EnableRefrigerantDetectionRepairFlow()
    flow.hass = hass
    flow.issue_id = issue_id
    flow.handler = DOMAIN
    flow.init_data = {"issue_id": issue_id}
    return flow


class TestEnableRefrigerantDetectionRepairFlow:
    """Tests for the EnableRefrigerantDetectionRepairFlow."""

    @pytest.mark.asyncio
    async def test_init_redirects_to_confirm(self, hass: HomeAssistant) -> None:
        """Verify async_step_init redirects to the confirm step."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        flow = await _init_repair_flow(
            hass, f"enable_refrigerant_detection_{entry.entry_id}"
        )

        result = await flow.async_step_init({"issue_id": "x"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

    @pytest.mark.asyncio
    async def test_confirm_shows_form(self, hass: HomeAssistant) -> None:
        """Verify the confirm step presents the consent form."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        flow = await _init_repair_flow(
            hass, f"enable_refrigerant_detection_{entry.entry_id}"
        )
        result = await flow.async_step_confirm()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

    @pytest.mark.asyncio
    async def test_confirm_enables(self, hass: HomeAssistant) -> None:
        """Selecting the toggle writes True to entry.options and finishes."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        flow = await _init_repair_flow(
            hass, f"enable_refrigerant_detection_{entry.entry_id}"
        )

        with patch.object(hass.config_entries, "async_reload"):
            result = await flow.async_step_confirm({CONF_REFRIGERANT_DETECTION: True})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_REFRIGERANT_DETECTION] is True

    @pytest.mark.asyncio
    async def test_confirm_declines(self, hass: HomeAssistant) -> None:
        """Declining writes False to entry.options and finishes."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        flow = await _init_repair_flow(
            hass, f"enable_refrigerant_detection_{entry.entry_id}"
        )

        with patch.object(hass.config_entries, "async_reload"):
            result = await flow.async_step_confirm({CONF_REFRIGERANT_DETECTION: False})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_REFRIGERANT_DETECTION] is False

    @pytest.mark.asyncio
    async def test_confirm_aborts_if_entry_not_found(self, hass: HomeAssistant) -> None:
        """The flow aborts when the config entry no longer exists."""
        flow = await _init_repair_flow(hass, "enable_refrigerant_detection_nonexistent")
        result = await flow.async_step_confirm()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "entry_not_found"

    @pytest.mark.asyncio
    async def test_confirm_deletes_issue(self, hass: HomeAssistant) -> None:
        """The repair issue is deleted after the flow completes."""
        entry = _make_entry()
        entry.add_to_hass(hass)

        issue_id = f"enable_refrigerant_detection_{entry.entry_id}"
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            issue_domain=DOMAIN,
            translation_key="enable_refrigerant_detection",
        )
        assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

        flow = await _init_repair_flow(hass, issue_id)
        with patch.object(hass.config_entries, "async_reload"):
            result = await flow.async_step_confirm({CONF_REFRIGERANT_DETECTION: True})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None

    @pytest.mark.asyncio
    async def test_confirm_preserves_existing_options(
        self, hass: HomeAssistant
    ) -> None:
        """The flow preserves other options already set on the entry."""
        entry = _make_entry(options={"some_other_option": "value"})
        entry.add_to_hass(hass)

        flow = await _init_repair_flow(
            hass, f"enable_refrigerant_detection_{entry.entry_id}"
        )

        with patch.object(hass.config_entries, "async_reload"):
            result = await flow.async_step_confirm({CONF_REFRIGERANT_DETECTION: True})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_REFRIGERANT_DETECTION] is True
        assert entry.options["some_other_option"] == "value"


def _should_create_issue(entry: MockConfigEntry) -> bool:
    """Replicate the __init__.py condition for the onboarding issue."""
    profile_cls = PROFILES[entry.data["profile"]]
    return (
        profile_cls().supports_extended_compressor_sensors
        and CONF_REFRIGERANT_DETECTION not in entry.options
    )


class TestRefrigerantOnboardingIssueCreation:
    """Tests for the onboarding repair-issue creation condition."""

    @pytest.mark.asyncio
    async def test_created_for_extended_profile_missing_option(
        self, hass: HomeAssistant
    ) -> None:
        """Created for a capable profile with no stored option."""
        entry = _make_entry(options={}, profile="yutaki_s")
        entry.add_to_hass(hass)

        assert _should_create_issue(entry) is True

    @pytest.mark.asyncio
    async def test_not_created_for_yutampo(self, hass: HomeAssistant) -> None:
        """Never created for a profile without extended compressor sensors."""
        entry = _make_entry(options={}, profile="yutampo_r32")
        entry.add_to_hass(hass)

        assert _should_create_issue(entry) is False

    @pytest.mark.asyncio
    async def test_not_created_when_option_already_set(
        self, hass: HomeAssistant
    ) -> None:
        """Not created once the user has already made a choice."""
        entry = _make_entry(
            options={CONF_REFRIGERANT_DETECTION: False}, profile="yutaki_s"
        )
        entry.add_to_hass(hass)

        assert _should_create_issue(entry) is False


class TestRefrigerantOnboardingDispatch:
    """Tests for async_create_fix_flow dispatching."""

    @pytest.mark.asyncio
    async def test_dispatches_refrigerant_onboarding_flow(
        self, hass: HomeAssistant
    ) -> None:
        """enable_refrigerant_detection_* issues get the onboarding flow."""
        flow = await async_create_fix_flow(
            hass, "enable_refrigerant_detection_some_entry", None
        )
        assert isinstance(flow, EnableRefrigerantDetectionRepairFlow)

    @pytest.mark.asyncio
    async def test_unknown_issue_gets_missing_config_flow(
        self, hass: HomeAssistant
    ) -> None:
        """Unknown issue types still fall back to MissingConfigRepairFlow."""
        flow = await async_create_fix_flow(hass, "unknown_issue_id", None)
        assert isinstance(flow, MissingConfigRepairFlow)
