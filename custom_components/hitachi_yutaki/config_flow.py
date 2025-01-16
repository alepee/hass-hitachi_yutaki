"""Config flow for Hitachi Yutaki integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CENTRAL_CONTROL_MODE_MAP,
    CONF_POWER_ENTITY,
    CONF_POWER_SUPPLY,
    CONF_VOLTAGE_ENTITY,
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_POWER_SUPPLY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
    REGISTER_CENTRAL_CONTROL_MODE,
    REGISTER_UNIT_MODEL,
)

_LOGGER = logging.getLogger(__name__)

# Basic schema for gateway configuration
GATEWAY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required("show_advanced", default=False): bool,
    }
)

# Schema for power supply configuration
POWER_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_POWER_SUPPLY, default=DEFAULT_POWER_SUPPLY
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["single", "three"],
                translation_key="power_supply",
            ),
        ),
        vol.Optional(CONF_VOLTAGE_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["sensor", "number", "input_number"],
            ),
        ),
        vol.Optional(CONF_POWER_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["sensor"],
                device_class=["power"],
            ),
        ),
        vol.Optional(CONF_WATER_INLET_TEMP_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["sensor", "number", "input_number"],
                device_class=["temperature"],
            ),
        ),
        vol.Optional(CONF_WATER_OUTLET_TEMP_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["sensor", "number", "input_number"],
                device_class=["temperature"],
            ),
        ),
    }
)

# Advanced schema
ADVANCED_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=247)
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
    MINOR_VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.basic_config = None
        self.show_advanced = False

    @staticmethod
    def is_matching(_, other_flow: dict) -> bool:
        """Test if the match dictionary matches this flow."""
        return True

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HitachiYutakiOptionsFlow:
        """Get the options flow for this handler."""
        return HitachiYutakiOptionsFlow(config_entry)

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
                CONF_PORT: user_input[CONF_PORT],
            }

            # Store advanced mode preference
            self.show_advanced = user_input["show_advanced"]

            # Go to power supply step
            return await self.async_step_power()

        return self.async_show_form(
            step_id="user",
            data_schema=GATEWAY_SCHEMA,
            errors=errors,
        )

    async def async_step_power(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle power supply configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.basic_config.update(user_input)

            if self.show_advanced:
                return await self.async_step_advanced()

            # Otherwise, proceed with default values
            return await self.async_validate_connection(
                {
                    **self.basic_config,
                    CONF_SLAVE: DEFAULT_SLAVE,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    "dev_mode": False,
                }
            )

        return self.async_show_form(
            step_id="power",
            data_schema=POWER_SCHEMA,
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
            from pymodbus.exceptions import ConnectionException, ModbusException

            client = ModbusTcpClient(
                host=config[CONF_HOST],
                port=config[CONF_PORT],
            )

            if not client.connect():
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="advanced" if "show_advanced" in config else "user",
                    data_schema=ADVANCED_SCHEMA
                    if "show_advanced" in config
                    else GATEWAY_SCHEMA,
                    errors=errors,
                )

            try:
                # Verify the device by checking unit model
                result = await self.hass.async_add_executor_job(
                    lambda addr=REGISTER_UNIT_MODEL: client.read_holding_registers(
                        address=addr,
                        count=1,
                        slave=config[CONF_SLAVE],
                    )
                )

                if result.isError():
                    errors["base"] = "invalid_slave"
                    return self.async_show_form(
                        step_id="advanced" if "show_advanced" in config else "user",
                        data_schema=ADVANCED_SCHEMA
                        if "show_advanced" in config
                        else GATEWAY_SCHEMA,
                        errors=errors,
                    )

                # Check central control mode
                mode_result = await self.hass.async_add_executor_job(
                    lambda addr=REGISTER_CENTRAL_CONTROL_MODE: client.read_holding_registers(
                        address=addr,
                        count=1,
                        slave=config[CONF_SLAVE],
                    )
                )

                if mode_result.isError():
                    errors["base"] = "modbus_error"
                    return self.async_show_form(
                        step_id="advanced" if "show_advanced" in config else "user",
                        data_schema=ADVANCED_SCHEMA
                        if "show_advanced" in config
                        else GATEWAY_SCHEMA,
                        errors=errors,
                    )

                if mode_result.registers[0] != CENTRAL_CONTROL_MODE_MAP["air"]:
                    errors["base"] = "invalid_central_control_mode"
                    return self.async_show_form(
                        step_id="advanced" if "show_advanced" in config else "user",
                        data_schema=ADVANCED_SCHEMA
                        if "show_advanced" in config
                        else GATEWAY_SCHEMA,
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

        except (ConnectionException, OSError):
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="advanced" if "show_advanced" in config else "user",
            data_schema=ADVANCED_SCHEMA
            if "show_advanced" in config
            else GATEWAY_SCHEMA,
            errors=errors,
        )


class HitachiYutakiOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Required(
                        CONF_POWER_SUPPLY,
                        default=self.config_entry.data.get(
                            CONF_POWER_SUPPLY, DEFAULT_POWER_SUPPLY
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["single", "three"],
                            translation_key="power_supply",
                        ),
                    ),
                    vol.Optional(CONF_VOLTAGE_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor", "number", "input_number"],
                        ),
                    ),
                    vol.Optional(CONF_POWER_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor"],
                            device_class=["power"],
                        ),
                    ),
                    vol.Optional(CONF_WATER_INLET_TEMP_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor", "number", "input_number"],
                            device_class=["temperature"],
                        ),
                    ),
                    vol.Optional(
                        CONF_WATER_OUTLET_TEMP_ENTITY
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor", "number", "input_number"],
                            device_class=["temperature"],
                        ),
                    ),
                }
            ),
        )
