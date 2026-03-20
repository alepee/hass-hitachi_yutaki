"""Config flow for Hitachi Yutaki integration."""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .api import GATEWAY_INFO, create_register_map
from .api.modbus.registers import GATEWAY_VARIANTS
from .const import (
    CONF_ENERGY_ENTITY,
    CONF_MODBUS_DEVICE_ID,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_POWER_ENTITY,
    CONF_POWER_SUPPLY,
    CONF_UNIT_ID,
    CONF_VOLTAGE_ENTITY,
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
    DEFAULT_DEVICE_ID,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_POWER_SUPPLY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
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
                translation_key="gateway_type",
            ),
        )
    }
)

# Basic schema for gateway configuration
GATEWAY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_MODBUS_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_MODBUS_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_MODBUS_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=247)
        ),
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
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
        vol.Optional(CONF_ENERGY_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["sensor"],
                device_class=["energy"],
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


class HitachiYutakiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hitachi Yutaki."""

    VERSION = 2
    MINOR_VERSION = 4

    def __init__(self):
        """Initialize the config flow."""
        self.gateway_type: str | None = None
        self.gateway_variant: str | None = None
        self.basic_config: dict[str, Any] = {}
        self.all_data: dict[str, Any] = {}
        self.detected_profiles: list[str] = []

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
        """Handle gateway configuration (connection test only)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store basic configuration
            self.basic_config = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_MODBUS_HOST: user_input[CONF_MODBUS_HOST],
                CONF_MODBUS_PORT: user_input[CONF_MODBUS_PORT],
                CONF_MODBUS_DEVICE_ID: user_input[CONF_MODBUS_DEVICE_ID],
                CONF_SCAN_INTERVAL: user_input.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            }
            # Store unit_id for HC-A(16/64)MB
            if self.gateway_type == "modbus_hc_a_mb":
                self.basic_config[CONF_UNIT_ID] = user_input.get(
                    CONF_UNIT_ID, DEFAULT_UNIT_ID
                )

            # Perform a basic connectivity test
            connection_ok = await self._test_connection()
            if not connection_ok:
                errors["base"] = "cannot_connect"
            else:
                # Connection successful — decide next step
                if self.gateway_type in GATEWAY_VARIANTS:
                    return await self.async_step_gateway_variant()
                # No variants — do profile detection directly
                profile_error = await self._detect_and_store_profiles()
                if profile_error:
                    errors["base"] = profile_error
                else:
                    return await self.async_step_profile()

        # Build schema dynamically based on gateway type
        schema = GATEWAY_SCHEMA
        if self.gateway_type == "modbus_hc_a_mb":
            schema = schema.extend(
                {
                    vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=15)
                    ),
                }
            )

        return self.async_show_form(
            step_id="gateway_config",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_gateway_variant(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle gateway variant (hardware generation) selection with auto-detection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.gateway_variant = user_input["gateway_variant"]
            # Now do profile detection with the chosen variant
            profile_error = await self._detect_and_store_profiles()
            if profile_error:
                errors["base"] = profile_error
            else:
                return await self.async_step_profile()

        # Try auto-detection of variant
        detected_variant = await self._detect_variant()

        variant_keys = list(GATEWAY_VARIANTS[self.gateway_type].keys())
        default_variant = detected_variant if detected_variant else vol.UNDEFINED

        # Build auto-detection status message for description
        if detected_variant:
            auto_detect_status = detected_variant.upper().replace("GEN", "Gen ")
        else:
            auto_detect_status = "?"

        return self.async_show_form(
            step_id="gateway_variant",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "gateway_variant",
                        default=default_variant,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=variant_keys,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="gateway_variant",
                        ),
                    ),
                }
            ),
            description_placeholders={
                "model_decoder_url": "https://alepee.github.io/hass-hitachi_yutaki/tools/model-decoder.html",
                "detected_variant": auto_detect_status,
            },
            errors=errors,
        )

    async def _test_connection(self) -> bool:
        """Test basic Modbus connectivity without reading registers.

        Creates a temporary API client and attempts to connect. For gateways
        without variants, this uses the correct register map. For gateways
        with variants, we use the default (gen2) register map just for the
        connectivity test — only connect + read system_state to verify
        the gateway is reachable.
        """
        api_client_class = GATEWAY_INFO[self.gateway_type].client_class
        # Use a default register map for connectivity test
        # For ATW-MBS-02 without variant selected yet, gen2 is fine for basic connectivity
        register_map = create_register_map(
            self.gateway_type,
            self.basic_config.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
            gateway_variant=self.gateway_variant,
        )
        api_client = api_client_class(
            self.hass,
            name=self.basic_config[CONF_NAME],
            host=self.basic_config[CONF_MODBUS_HOST],
            port=self.basic_config[CONF_MODBUS_PORT],
            slave=self.basic_config[CONF_MODBUS_DEVICE_ID],
            register_map=register_map,
        )
        try:
            if not await api_client.connect():
                return False
            # Read system_state as a basic preflight check
            # This register is at the same address in all ATW-MBS-02 variants
            await api_client.read_values(api_client.register_map.gateway_keys)
            return True
        except (ModbusException, ConnectionException, OSError):
            return False
        finally:
            if api_client.connected:
                await api_client.close()

    async def _detect_variant(self) -> str | None:
        """Try to auto-detect the gateway variant by probing with each register map.

        Strategy: create a client with the gen2 register map, connect, read unit_model.
        If the deserialized value is a known model, it's gen2. Otherwise try gen1.
        """
        variants = GATEWAY_VARIANTS.get(self.gateway_type, {})
        if not variants:
            return None

        api_client_class = GATEWAY_INFO[self.gateway_type].client_class

        # Try gen2 first (more common, newer hardware)
        for variant_key in ["gen2", "gen1"]:
            if variant_key not in variants:
                continue
            register_map = create_register_map(
                self.gateway_type,
                self.basic_config.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
                gateway_variant=variant_key,
            )
            api_client = api_client_class(
                self.hass,
                name="variant_probe",
                host=self.basic_config[CONF_MODBUS_HOST],
                port=self.basic_config[CONF_MODBUS_PORT],
                slave=self.basic_config[CONF_MODBUS_DEVICE_ID],
                register_map=register_map,
            )
            try:
                if not await api_client.connect():
                    return None
                # Read gateway keys which include unit_model
                await api_client.read_values(api_client.register_map.gateway_keys)
                unit_model = await api_client.read_value("unit_model")
                if unit_model is not None and unit_model != "unknown":
                    _LOGGER.debug(
                        "Auto-detected variant %s (unit_model=%s)",
                        variant_key,
                        unit_model,
                    )
                    return variant_key
            except (ModbusException, ConnectionException, OSError):
                _LOGGER.debug(
                    "Variant probe failed for %s",
                    variant_key,
                )
            finally:
                if api_client.connected:
                    await api_client.close()

        return None

    async def _detect_and_store_profiles(self) -> str | None:
        """Connect to gateway, read data, detect profiles.

        Returns None on success, or an error key string on failure.
        Sets self.detected_profiles on success.
        """
        api_client_class = GATEWAY_INFO[self.gateway_type].client_class
        register_map = create_register_map(
            self.gateway_type,
            self.basic_config.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
            gateway_variant=self.gateway_variant,
        )
        api_client = api_client_class(
            self.hass,
            name=self.basic_config[CONF_NAME],
            host=self.basic_config[CONF_MODBUS_HOST],
            port=self.basic_config[CONF_MODBUS_PORT],
            slave=self.basic_config[CONF_MODBUS_DEVICE_ID],
            register_map=register_map,
        )
        try:
            if not await api_client.connect():
                return "cannot_connect"

            _LOGGER.debug("Fetching all values to allow profiles to detect device")
            keys_to_read = api_client.register_map.base_keys
            await api_client.read_values(keys_to_read)
            all_data = {key: await api_client.read_value(key) for key in keys_to_read}

            # Decode the raw config to get boolean flags
            decoded_data = api_client.decode_config(all_data)

            _LOGGER.debug("Detecting profile with data: %s", decoded_data)
            detected_profiles = [
                key for key, profile in PROFILES.items() if profile.detect(decoded_data)
            ]

            _LOGGER.debug("Detected profiles: %s", detected_profiles)
            self.detected_profiles = detected_profiles

            if not detected_profiles:
                _LOGGER.warning("No profile detected, showing all available profiles")
            return None
        except (ModbusException, ConnectionException, OSError):
            return "cannot_connect"
        finally:
            if api_client.connected:
                await api_client.close()

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle profile selection."""
        if user_input is not None:
            self.basic_config["profile"] = user_input["profile"]
            # Go to power supply step
            return await self.async_step_power()

        # Schema for profile selection
        # Show all available profiles so user can manually select their machine
        profile_options = list(PROFILES.keys())
        # Use first detected profile if available, otherwise use UNDEFINED to force user selection
        default_profile = (
            self.detected_profiles[0] if self.detected_profiles else vol.UNDEFINED
        )
        PROFILE_SCHEMA = vol.Schema(
            {
                vol.Required(
                    "profile", default=default_profile
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=profile_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="profile",
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
            config = {
                "gateway_type": self.gateway_type,
                **self.basic_config,
            }
            if self.gateway_variant is not None:
                config["gateway_variant"] = self.gateway_variant
            return await self.async_validate_connection(config)

        return self.async_show_form(
            step_id="power",
            data_schema=POWER_SCHEMA,
            errors=errors,
        )

    async def async_validate_connection(self, config: dict) -> FlowResult:
        """Validate the Modbus connection."""
        errors: dict[str, str] = {}

        api_client_class = GATEWAY_INFO[config["gateway_type"]].client_class
        register_map = create_register_map(
            config["gateway_type"],
            config.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
            gateway_variant=config.get("gateway_variant"),
        )
        api_client = api_client_class(
            self.hass,
            name=config[CONF_NAME],
            host=config[CONF_MODBUS_HOST],
            port=config[CONF_MODBUS_PORT],
            slave=config[CONF_MODBUS_DEVICE_ID],
            register_map=register_map,
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
                        # Try to get hardware-based unique_id from Modbus input registers
                        hw_id = await api_client.async_get_unique_id()

                        if hw_id:
                            # Use hardware identifier with domain prefix
                            unique_id = f"{DOMAIN}_{hw_id}"
                            _LOGGER.info(
                                "Gateway hardware identifier detected: %s",
                                unique_id,
                            )
                        else:
                            # Fallback to IP+slave if Modbus read failed
                            unique_id = f"{config[CONF_MODBUS_HOST]}_{config[CONF_MODBUS_DEVICE_ID]}"
                            _LOGGER.warning(
                                "Could not retrieve gateway hardware identifier. "
                                "Using IP-based unique_id: %s. "
                                "Duplicate detection will be limited.",
                                unique_id,
                            )

                        await self.async_set_unique_id(unique_id)
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=config[CONF_NAME],
                            data=config,
                        )
                    else:
                        errors["base"] = "invalid_slave"

        except (ModbusException, ConnectionException, OSError):
            errors["base"] = "cannot_connect"
        finally:
            if api_client.connected:
                await api_client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=GATEWAY_SCHEMA,
            errors=errors,
        )


class HitachiYutakiOptionsFlow(config_entries.OptionsFlow):
    """Handle options as a multi-step flow mirroring initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._collected: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Gateway type selection."""
        if user_input is not None:
            self._collected.update(user_input)
            return await self.async_step_connection()

        current_gateway = self.config_entry.data.get(
            "gateway_type", "modbus_atw_mbs_02"
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "gateway_type", default=current_gateway
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(GATEWAY_INFO.keys()),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="gateway_type",
                        ),
                    ),
                }
            ),
        )

    async def async_step_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Connection settings."""
        if user_input is not None:
            self._collected.update(user_input)
            gateway_type = self._collected.get(
                "gateway_type", self.config_entry.data.get("gateway_type")
            )
            if gateway_type in GATEWAY_VARIANTS:
                return await self.async_step_gateway_variant()
            return await self.async_step_profile()

        data = self.config_entry.data

        return self.async_show_form(
            step_id="connection",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODBUS_HOST, default=data.get(CONF_MODBUS_HOST)
                    ): str,
                    vol.Required(
                        CONF_MODBUS_PORT, default=data.get(CONF_MODBUS_PORT)
                    ): cv.port,
                    vol.Required(
                        CONF_MODBUS_DEVICE_ID,
                        default=data.get(CONF_MODBUS_DEVICE_ID, DEFAULT_DEVICE_ID),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): cv.positive_int,
                }
            ),
        )

    async def async_step_gateway_variant(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2b: Gateway variant (hardware generation) selection."""
        if user_input is not None:
            self._collected.update(user_input)
            return await self.async_step_profile()

        gateway_type = self._collected.get(
            "gateway_type", self.config_entry.data.get("gateway_type")
        )
        variant_keys = list(GATEWAY_VARIANTS[gateway_type].keys())
        current_variant = self.config_entry.data.get("gateway_variant", "gen2")

        return self.async_show_form(
            step_id="gateway_variant",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "gateway_variant", default=current_variant
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=variant_keys,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="gateway_variant",
                        ),
                    ),
                }
            ),
            description_placeholders={
                "model_decoder_url": "https://alepee.github.io/hass-hitachi_yutaki/tools/model-decoder.html",
            },
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Profile selection."""
        if user_input is not None:
            self._collected.update(user_input)
            return await self.async_step_sensors()

        current_profile = self.config_entry.data.get("profile", vol.UNDEFINED)

        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "profile", default=current_profile
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(PROFILES.keys()),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="profile",
                        ),
                    ),
                }
            ),
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Power supply and external sensors."""
        if user_input is not None:
            self._collected.update(user_input)

            # Merge collected values into entry.data and reload
            new_data = {**self.config_entry.data, **self._collected}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )
            return self.async_create_entry(title="", data={})

        data = self.config_entry.data

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POWER_SUPPLY,
                        default=data.get(CONF_POWER_SUPPLY, DEFAULT_POWER_SUPPLY),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["single", "three"],
                            translation_key="power_supply",
                        ),
                    ),
                    vol.Optional(
                        CONF_VOLTAGE_ENTITY,
                        default=(
                            data.get(CONF_VOLTAGE_ENTITY)
                            if data.get(CONF_VOLTAGE_ENTITY) is not None
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
                            data.get(CONF_POWER_ENTITY)
                            if data.get(CONF_POWER_ENTITY) is not None
                            else vol.UNDEFINED
                        ),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor"],
                            device_class=["power"],
                        ),
                    ),
                    vol.Optional(
                        CONF_ENERGY_ENTITY,
                        default=(
                            data.get(CONF_ENERGY_ENTITY)
                            if data.get(CONF_ENERGY_ENTITY) is not None
                            else vol.UNDEFINED
                        ),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor"],
                            device_class=["energy"],
                        ),
                    ),
                    vol.Optional(
                        CONF_WATER_INLET_TEMP_ENTITY,
                        default=(
                            data.get(CONF_WATER_INLET_TEMP_ENTITY)
                            if data.get(CONF_WATER_INLET_TEMP_ENTITY) is not None
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
                            data.get(CONF_WATER_OUTLET_TEMP_ENTITY)
                            if data.get(CONF_WATER_OUTLET_TEMP_ENTITY) is not None
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
