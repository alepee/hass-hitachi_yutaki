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
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    REGISTER_UNIT_MODEL,
    REGISTER_CENTRAL_CONTROL_MODE,
    CENTRAL_CONTROL_MODE_MAP,
)

_LOGGER = logging.getLogger(__name__)

# Basic schema with essential options and advanced mode checkbox
BASE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required("show_advanced", default=False): bool,
    }
)

# Advanced schema with additional options
ADVANCED_SCHEMA = vol.Schema(
    {
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
        self.basic_config = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store basic configuration
            self.basic_config = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_NAME: user_input[CONF_NAME],
            }

            # If advanced mode is selected, go to advanced step
            if user_input["show_advanced"]:
                return await self.async_step_advanced()

            # Otherwise, proceed with default values
            return await self.async_validate_connection({
                **self.basic_config,
                CONF_PORT: DEFAULT_PORT,
                CONF_SLAVE: DEFAULT_SLAVE,
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                "dev_mode": False,
            })

        return self.async_show_form(
            step_id="user",
            data_schema=BASE_SCHEMA,
            errors=errors,
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle advanced configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Combine basic and advanced configurations
            complete_config = {
                **self.basic_config,
                **user_input,
            }
            return await self.async_validate_connection(complete_config)

        return self.async_show_form(
            step_id="advanced",
            data_schema=ADVANCED_SCHEMA,
            errors=errors,
        )

    async def async_validate_connection(self, config: dict) -> FlowResult:
        """Validate the Modbus connection."""
        errors: dict[str, str] = {}

        try:
            from pymodbus.client import ModbusTcpClient
            from pymodbus.exceptions import ModbusException

            client = ModbusTcpClient(
                host=config[CONF_HOST],
                port=config[CONF_PORT],
            )

            if not client.connect():
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="advanced" if "show_advanced" in config else "user",
                    data_schema=ADVANCED_SCHEMA if "show_advanced" in config else BASE_SCHEMA,
                    errors=errors,
                )

            try:
                # Verify the device by checking unit model
                result = await self.hass.async_add_executor_job(
                    client.read_holding_registers,
                    REGISTER_UNIT_MODEL,
                    1,
                    config[CONF_SLAVE],
                )

                if result.isError():
                    errors["base"] = "invalid_slave"
                    return self.async_show_form(
                        step_id="advanced" if "show_advanced" in config else "user",
                        data_schema=ADVANCED_SCHEMA if "show_advanced" in config else BASE_SCHEMA,
                        errors=errors,
                    )

                # Check central control mode
                mode_result = await self.hass.async_add_executor_job(
                    client.read_holding_registers,
                    REGISTER_CENTRAL_CONTROL_MODE,
                    1,
                    config[CONF_SLAVE],
                )

                if mode_result.isError():
                    errors["base"] = "modbus_error"
                    return self.async_show_form(
                        step_id="advanced" if "show_advanced" in config else "user",
                        data_schema=ADVANCED_SCHEMA if "show_advanced" in config else BASE_SCHEMA,
                        errors=errors,
                    )

                if mode_result.registers[0] != CENTRAL_CONTROL_MODE_MAP["air"]:
                    errors["base"] = "invalid_central_control_mode"
                    return self.async_show_form(
                        step_id="advanced" if "show_advanced" in config else "user",
                        data_schema=ADVANCED_SCHEMA if "show_advanced" in config else BASE_SCHEMA,
                        errors=errors,
                    )

                # Create entry if all validations pass
                await self.async_set_unique_id(
                    f"{config[CONF_HOST]}_{config[CONF_SLAVE]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=config[CONF_NAME],
                    data={k: v for k, v in config.items() if k != "show_advanced"},
                )

            except ModbusException:
                errors["base"] = "modbus_error"
            finally:
                client.close()

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="advanced" if "show_advanced" in config else "user",
            data_schema=ADVANCED_SCHEMA if "show_advanced" in config else BASE_SCHEMA,
            errors=errors,
        )
