"""Repairs platform for Hitachi Yutaki integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.issue_registry import async_delete_issue

from .api import GATEWAY_INFO
from .const import DOMAIN
from .profiles import PROFILES


class MissingConfigRepairFlow(RepairsFlow):
    """Handler for repair flows to fix missing configuration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial repair step."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the confirmation step with form."""
        # Extract entry_id from issue_id
        # Format: "missing_config_{entry_id}"
        entry_id = self.issue_id.replace("missing_config_", "")

        # Find the corresponding config entry
        config_entries = self.hass.config_entries.async_entries(DOMAIN)
        entry = next((e for e in config_entries if e.entry_id == entry_id), None)

        if entry is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            # Update the config entry with the missing parameters
            new_data = {
                **entry.data,
                "gateway_type": user_input.get("gateway_type", "modbus_atw_mbs_02"),
                "profile": user_input.get("profile"),
            }

            self.hass.config_entries.async_update_entry(entry, data=new_data)

            # Clear the repair issue
            async_delete_issue(self.hass, DOMAIN, self.issue_id)

            # Auto-reload the integration to apply changes
            await self.hass.config_entries.async_reload(entry.entry_id)

            return self.async_create_entry(data={})

        # Show repair form
        gateway_options = list(GATEWAY_INFO.keys())
        profile_options = list(PROFILES.keys())

        schema = vol.Schema(
            {
                vol.Required(
                    "gateway_type",
                    default=gateway_options[0]
                    if gateway_options
                    else "modbus_atw_mbs_02",
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=gateway_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Required(
                    "profile", default=profile_options[0] if profile_options else None
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=profile_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
            }
        )

        return self.async_show_form(step_id="confirm", data_schema=schema)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow for missing configuration."""
    return MissingConfigRepairFlow()
