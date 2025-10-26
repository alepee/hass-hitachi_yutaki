"""Repair flow for Hitachi Yutaki integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .api import GATEWAY_INFO
from .const import (
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SLAVE,
)
from .profiles import PROFILES

_LOGGER = logging.getLogger(__name__)


class HitachiYutakiRepairFlow(config_entries.ConfigFlow):
    """Handle repair flow for Hitachi Yutaki."""

    VERSION = 1

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize repair flow."""
        self.config_entry = config_entry
        self.gateway_type: str | None = None
        self.basic_config: dict[str, Any] = {}
        self.detected_profiles: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial repair step."""
        if user_input is not None:
            self.gateway_type = user_input["gateway_type"]
            return await self.async_step_gateway_config()

        # Pre-fill with existing config data
        gateway_options = list(GATEWAY_INFO.keys())
        default_gateway = gateway_options[0] if gateway_options else "modbus_atw_mbs_02"

        schema = vol.Schema(
            {
                vol.Required(
                    "gateway_type", default=default_gateway
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=gateway_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                )
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={
                "integration_name": self.config_entry.data.get(
                    CONF_NAME, "Hitachi Yutaki"
                ),
            },
        )

    async def async_step_gateway_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle gateway configuration step."""
        if user_input is not None:
            # Store basic configuration
            self.basic_config = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_NAME: user_input[CONF_NAME],
                CONF_PORT: user_input[CONF_PORT],
            }

            # Validate connection and detect profile
            api_client_class = GATEWAY_INFO[self.gateway_type].client_class
            api_client = api_client_class(
                self.hass,
                name=user_input[CONF_NAME],
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                slave=DEFAULT_SLAVE,
            )

            try:
                if await api_client.connect():
                    # Read gateway data for profile detection
                    await api_client.read_values(api_client.register_map.gateway_keys)
                    model_key = await api_client.get_model_key()

                    if model_key:
                        # Detect compatible profiles
                        self.detected_profiles = []
                        for profile_key, profile_class in PROFILES.items():
                            profile_instance = profile_class()
                            if profile_instance.detect({"unit_model": model_key}):
                                self.detected_profiles.append(profile_key)

                        if self.detected_profiles:
                            return await self.async_step_profile()
                        else:
                            return self.async_show_abort(
                                reason="no_profile_detected",
                                description_placeholders={
                                    "model": model_key,
                                },
                            )
                    else:
                        return self.async_show_abort(
                            reason="invalid_slave",
                            description_placeholders={
                                "slave": str(DEFAULT_SLAVE),
                            },
                        )
                else:
                    return self.async_show_abort(
                        reason="cannot_connect",
                        description_placeholders={
                            "host": user_input[CONF_HOST],
                            "port": str(user_input[CONF_PORT]),
                        },
                    )
            except Exception as ex:
                _LOGGER.error("Error during repair flow: %s", ex)
                return self.async_show_abort(
                    reason="connection_error",
                    description_placeholders={
                        "error": str(ex),
                    },
                )
            finally:
                if api_client.connected:
                    await api_client.close()

        # Pre-fill with existing config data
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NAME,
                    default=self.config_entry.data.get(CONF_NAME, DEFAULT_NAME),
                ): str,
                vol.Required(
                    CONF_HOST,
                    default=self.config_entry.data.get(CONF_HOST, DEFAULT_HOST),
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=self.config_entry.data.get(CONF_PORT, DEFAULT_PORT),
                ): cv.port,
            }
        )

        return self.async_show_form(
            step_id="gateway_config",
            data_schema=schema,
            description_placeholders={
                "gateway_type": self.gateway_type,
            },
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle profile selection step."""
        if user_input is not None:
            # Update the config entry with the new data
            new_data = {
                **self.config_entry.data,
                "gateway_type": self.gateway_type,
                "profile": user_input["profile"],
                **self.basic_config,
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            return self.async_create_entry(
                title=f"Repaired {self.config_entry.data.get(CONF_NAME, 'Hitachi Yutaki')}",
                data={},
            )

        # Pre-fill with detected profile if only one is detected
        default_profile = (
            self.detected_profiles[0] if len(self.detected_profiles) == 1 else None
        )

        schema = vol.Schema(
            {
                vol.Required(
                    "profile", default=default_profile
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self.detected_profiles,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                )
            }
        )

        return self.async_show_form(
            step_id="profile",
            data_schema=schema,
            description_placeholders={
                "detected_profiles": ", ".join(self.detected_profiles),
            },
        )


async def async_create_repair_flow(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> HitachiYutakiRepairFlow:
    """Create a repair flow for the given config entry."""
    return HitachiYutakiRepairFlow(config_entry)
