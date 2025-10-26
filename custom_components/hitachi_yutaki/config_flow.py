"""Config flow for Hitachi Yutaki integration."""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException
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

from .api import GATEWAY_INFO
from .const import (
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
)
from .profiles import PROFILES

_LOGGER = logging.getLogger(__name__)

# Schema for gateway selection
GATEWAY_SELECTION_SCHEMA = vol.Schema(
    {
        vol.Required("gateway_type"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(GATEWAY_INFO.keys()),
                mode=selector.SelectSelectorMode.DROPDOWN,
            ),
        )
    }
)

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

    VERSION = 2
    MINOR_VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.gateway_type: str | None = None
        self.basic_config: dict[str, Any] = {}
        self.all_data: dict[str, Any] = {}
        self.detected_profiles: list[str] = []
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
        """Handle the initial step (gateway selection)."""
        if user_input is not None:
            self.gateway_type = user_input["gateway_type"]
            return await self.async_step_gateway_config()

        return self.async_show_form(
            step_id="user", data_schema=GATEWAY_SELECTION_SCHEMA
        )

    async def async_step_gateway_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle gateway configuration."""
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

            # Validate connection and read all data for detection
            api_client_class = GATEWAY_INFO[self.gateway_type].client_class
            api_client = api_client_class(
                self.hass,
                name=user_input[CONF_NAME],
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                slave=DEFAULT_SLAVE,  # Use default for initial check
            )
            try:
                if not await api_client.connect():
                    errors["base"] = "cannot_connect"
                else:
                    _LOGGER.debug(
                        "Fetching all values to allow profiles to detect device"
                    )
                    keys_to_read = api_client.register_map.base_keys
                    await api_client.read_values(keys_to_read)
                    all_data = {
                        key: await api_client.read_value(key) for key in keys_to_read
                    }

                    # Decode the raw config to get boolean flags
                    decoded_data = api_client.decode_config(all_data)

                    _LOGGER.debug("Detecting profile with data: %s", decoded_data)
                    detected_profiles = [
                        key
                        for key, profile in PROFILES.items()
                        if profile.detect(decoded_data)
                    ]

                    _LOGGER.debug("Detected profiles: %s", detected_profiles)
                    self.detected_profiles = detected_profiles

                    if not detected_profiles:
                        _LOGGER.warning(
                            "No profile detected, showing all available profiles"
                        )
                    return await self.async_step_profile()
            except (ModbusException, ConnectionException, OSError):
                errors["base"] = "cannot_connect"
            finally:
                if api_client.connected:
                    await api_client.close()

        return self.async_show_form(
            step_id="gateway_config",
            data_schema=GATEWAY_SCHEMA,
            errors=errors,
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle profile selection."""
        if user_input is not None:
            self.basic_config["profile"] = user_input["profile"]
            # Go to power supply step
            return await self.async_step_power()

        # Schema for profile selection
        profile_options = list(PROFILES.keys())
        PROFILE_SCHEMA = vol.Schema(
            {
                vol.Required(
                    "profile", default=self.detected_profiles[0]
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=profile_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(step_id="profile", data_schema=PROFILE_SCHEMA)

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
                    "gateway_type": self.gateway_type,
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
                "gateway_type": self.gateway_type,
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

        api_client_class = GATEWAY_INFO[config["gateway_type"]].client_class
        api_client = api_client_class(
            self.hass,
            name=config[CONF_NAME],
            host=config[CONF_HOST],
            port=config[CONF_PORT],
            slave=config[CONF_SLAVE],
        )

        try:
            if not await api_client.connect():
                errors["base"] = "cannot_connect"
            else:
                # Use the update method to fetch initial data for validation
                await api_client.read_values(api_client.register_map.gateway_keys)

                system_state = await api_client.read_value("system_state")
                if system_state == 2:  # Data init
                    errors["base"] = "system_initializing"
                elif system_state == 1:  # Desync
                    errors["base"] = "desync_error"
                else:
                    # Further checks can be added here if needed
                    model_key = await api_client.get_model_key()
                    if model_key:
                        await self.async_set_unique_id(
                            f"{config[CONF_HOST]}_{config[CONF_SLAVE]}"
                        )
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=config[CONF_NAME],
                            data={
                                k: v for k, v in config.items() if k != "show_advanced"
                            },
                        )
                    else:
                        errors["base"] = "invalid_slave"

        except (ModbusException, ConnectionException, OSError):
            errors["base"] = "cannot_connect"
        finally:
            if api_client.connected:
                await api_client.close()

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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        # Access the current entry using the base class attribute
        # available during option flows.
        config_data = self.config_entry.data  # type: ignore[attr-defined]
        options_data = self.config_entry.options  # type: ignore[attr-defined]

        # Check if we need to repair missing configuration
        missing_params = []
        if "gateway_type" not in config_data:
            missing_params.append("gateway_type")
        if "profile" not in config_data:
            missing_params.append("profile")

        if missing_params:
            # Redirect to repair step
            return await self.async_step_repair()

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=options_data.get(CONF_HOST, config_data.get(CONF_HOST)),
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=options_data.get(CONF_PORT, config_data.get(CONF_PORT)),
                    ): cv.port,
                    vol.Required(
                        CONF_POWER_SUPPLY,
                        default=options_data.get(
                            CONF_POWER_SUPPLY,
                            config_data.get(CONF_POWER_SUPPLY, DEFAULT_POWER_SUPPLY),
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["single", "three"],
                            translation_key="power_supply",
                        ),
                    ),
                    vol.Optional(
                        CONF_VOLTAGE_ENTITY,
                        default=(
                            options_data.get(CONF_VOLTAGE_ENTITY)
                            if options_data.get(CONF_VOLTAGE_ENTITY) is not None
                            else vol.UNDEFINED
                        ),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor", "number", "input_number"],
                        ),
                    ),
                    vol.Optional(
                        CONF_POWER_ENTITY,
                        default=(
                            options_data.get(CONF_POWER_ENTITY)
                            if options_data.get(CONF_POWER_ENTITY) is not None
                            else vol.UNDEFINED
                        ),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor"],
                            device_class=["power"],
                        ),
                    ),
                    vol.Optional(
                        CONF_WATER_INLET_TEMP_ENTITY,
                        default=(
                            options_data.get(CONF_WATER_INLET_TEMP_ENTITY)
                            if options_data.get(CONF_WATER_INLET_TEMP_ENTITY)
                            is not None
                            else vol.UNDEFINED
                        ),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor", "number", "input_number"],
                            device_class=["temperature"],
                        ),
                    ),
                    vol.Optional(
                        CONF_WATER_OUTLET_TEMP_ENTITY,
                        default=(
                            options_data.get(CONF_WATER_OUTLET_TEMP_ENTITY)
                            if options_data.get(CONF_WATER_OUTLET_TEMP_ENTITY)
                            is not None
                            else vol.UNDEFINED
                        ),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor", "number", "input_number"],
                            device_class=["temperature"],
                        ),
                    ),
                }
            ),
        )

    async def async_step_repair(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle repair step for missing configuration."""
        config_data = self.config_entry.data  # type: ignore[attr-defined]

        if user_input is not None:
            # Update the config entry with the missing parameters
            new_data = {
                **config_data,
                "gateway_type": user_input.get("gateway_type", "modbus_atw_mbs_02"),
                "profile": user_input.get("profile"),
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            # Clear the repair issue
            from homeassistant.helpers.issue_registry import async_delete_issue

            async_delete_issue(
                self.hass,
                DOMAIN,
                f"missing_config_{self.config_entry.entry_id}",
            )

            return self.async_create_entry(
                title="Configuration repaired",
                data={},
            )

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

        return self.async_show_form(
            step_id="repair",
            data_schema=schema,
            description_placeholders={
                "integration_name": config_data.get(CONF_NAME, "Hitachi Yutaki"),
            },
        )
