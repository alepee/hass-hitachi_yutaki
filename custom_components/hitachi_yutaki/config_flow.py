"""Config flow for Hitachi Yutaki integration."""
from __future__ import annotations
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_NAME,
    CONF_SLAVE,
    CONF_SCAN_INTERVAL,
)
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    REGISTER_UNIT_MODEL,
    REGISTER_CENTRAL_CONTROL_MODE,
    CENTRAL_CONTROL_MODE_MAP,
)

_LOGGER = logging.getLogger(__name__)

# Schema for mode selection (simple/advanced)
MODE_SCHEMA = vol.Schema(
    {
        vol.Required("advanced_mode", default=False): bool,
    }
)

# Basic schema with essential options only
BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)

# Advanced schema with all available options
ADVANCED_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): vol.All(
            cv.positive_int, vol.Range(min=1, max=247)
        ),
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional("dev_mode", default=False): bool,
    }
)


class HitachiYutakiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hitachi Yutaki."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        # Store the mode choice and user input throughout the flow
        self.advanced_mode = False
        self.user_input = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initial step - redirect to mode selection."""
        return self.async_show_form(
            step_id="choose_mode",
            data_schema=MODE_SCHEMA,
        )

    async def async_step_choose_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let user choose between simple and advanced configuration mode."""
        if user_input is not None:
            # Store the mode choice and move to configuration step
            self.advanced_mode = user_input["advanced_mode"]
            return await self.async_step_configure()

        return self.async_show_form(
            step_id="choose_mode",
            data_schema=MODE_SCHEMA,
        )

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the configuration step."""
        errors: dict[str, str] = {}
        # Select schema based on chosen mode
        schema = ADVANCED_SCHEMA if self.advanced_mode else BASE_SCHEMA

        if user_input is None:
            # Show the form if no user input
            return self.async_show_form(
                step_id="configure",
                data_schema=schema,
                errors=errors,
            )

        # If in simple mode, add default values for advanced options
        if not self.advanced_mode:
            user_input = {
                **user_input,
                CONF_PORT: DEFAULT_PORT,
                CONF_SLAVE: DEFAULT_SLAVE,
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                "dev_mode": False,
            }

        try:
            # Try to connect to the Modbus device
            from pymodbus.client import ModbusTcpClient
            from pymodbus.exceptions import ModbusException

            client = ModbusTcpClient(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
            )

            if not client.connect():
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="configure", data_schema=schema, errors=errors
                )

            try:
                # Verify the device by checking unit model
                result = await self.hass.async_add_executor_job(
                    client.read_holding_registers,
                    REGISTER_UNIT_MODEL,
                    1,
                    user_input[CONF_SLAVE],
                )

                if result.isError():
                    errors["base"] = "invalid_slave"
                    return self.async_show_form(
                        step_id="configure", data_schema=schema, errors=errors
                    )

                # Check if central control mode is correct
                mode_result = await self.hass.async_add_executor_job(
                    client.read_holding_registers,
                    REGISTER_CENTRAL_CONTROL_MODE,
                    1,
                    user_input[CONF_SLAVE],
                )

                if mode_result.isError():
                    errors["base"] = "modbus_error"
                    return self.async_show_form(
                        step_id="configure", data_schema=schema, errors=errors
                    )

                if mode_result.registers[0] != CENTRAL_CONTROL_MODE_MAP["air"]:
                    errors["base"] = "invalid_central_control_mode"
                    return self.async_show_form(
                        step_id="configure", data_schema=schema, errors=errors
                    )

                # Create entry if all validations pass
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}_{user_input[CONF_SLAVE]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        **user_input,
                        "dev_mode": user_input.get("dev_mode", False),
                    },
                )

            except ModbusException:
                errors["base"] = "modbus_error"
            finally:
                client.close()

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="configure", data_schema=schema, errors=errors
        )
