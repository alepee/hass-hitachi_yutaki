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

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): vol.All(
            cv.positive_int, vol.Range(min=1, max=247)
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional("dev_mode", default=False): bool,
    }
)


class HitachiYutakiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hitachi Yutaki."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        try:
            from pymodbus.client import ModbusTcpClient
            from pymodbus.exceptions import ModbusException

            client = ModbusTcpClient(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
            )

            if not client.connect():
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                )

            try:
                # Check unit model
                result = await self.hass.async_add_executor_job(
                    client.read_holding_registers,
                    REGISTER_UNIT_MODEL,
                    1,
                    user_input[CONF_SLAVE],
                )

                if result.isError():
                    errors["base"] = "invalid_slave"
                    return self.async_show_form(
                        step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                    )

                # Check central control mode
                mode_result = await self.hass.async_add_executor_job(
                    client.read_holding_registers,
                    REGISTER_CENTRAL_CONTROL_MODE,
                    1,
                    user_input[CONF_SLAVE],
                )

                if mode_result.isError():
                    errors["base"] = "modbus_error"
                    return self.async_show_form(
                        step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                    )

                if mode_result.registers[0] != CENTRAL_CONTROL_MODE_MAP["air"]:
                    errors["base"] = "invalid_central_control_mode"
                    return self.async_show_form(
                        step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                    )

                # Create entry if everything is OK
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
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
