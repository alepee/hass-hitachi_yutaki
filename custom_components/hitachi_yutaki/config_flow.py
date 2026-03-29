"""Config flow for Hitachi Yutaki integration."""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import GATEWAY_INFO, create_register_map
from .api.config_providers import GATEWAY_CONFIG_PROVIDERS, GatewayConfigProvider
from .const import (
    CONF_ENERGY_ENTITY,
    CONF_MODBUS_DEVICE_ID,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_POWER_ENTITY,
    CONF_POWER_SUPPLY,
    CONF_TELEMETRY_LEVEL,
    CONF_UNIT_ID,
    CONF_VOLTAGE_ENTITY,
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
    DEFAULT_POWER_SUPPLY,
    DEFAULT_TELEMETRY_LEVEL,
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
        self._provider: GatewayConfigProvider | None = None
        self._provider_steps: list[str] = []
        self._current_step_index: int = 0
        self._step_context: dict[str, Any] = {}
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
            if self.gateway_type not in GATEWAY_CONFIG_PROVIDERS:
                return self.async_abort(reason="unknown_gateway")
            self._provider = GATEWAY_CONFIG_PROVIDERS[self.gateway_type]()
            self._provider_steps = self._provider.config_steps()
            self._current_step_index = 0

            # Register dynamic step methods for HA routing.
            # HA dispatches form submissions by calling async_step_<step_id>()
            # via introspection. Since provider step IDs are dynamic (declared
            # at runtime by each gateway), we register them here so HA can
            # find them. Each handler captures its step index via
            # _make_step_handler to ensure correct routing even if steps
            # are called out of order.
            for idx, step_id in enumerate(self._provider_steps):
                setattr(
                    self,
                    f"async_step_{step_id}",
                    self._make_step_handler(idx),
                )

            return await self._handle_provider_step()

        return self.async_show_form(
            step_id="user", data_schema=GATEWAY_SELECTION_SCHEMA
        )

    def _make_step_handler(self, step_idx: int):
        """Create a step handler bound to a specific provider step index.

        HA dispatches form submissions by calling async_step_<step_id>()
        via introspection. Each handler captures its step index to ensure
        the correct provider step is processed, even if steps are called
        out of order.
        """

        async def handler(user_input=None):
            self._current_step_index = step_idx
            return await self._handle_provider_step(user_input)

        return handler

    async def _handle_provider_step(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a gateway provider configuration step.

        Process every step declared by the gateway's GatewayConfigProvider.
        HA routes to this method via dynamically registered
        async_step_<step_id> methods (see async_step_user).

        Flow:
        1. First call (user_input=None): get schema from provider, show form
        2. Submission (user_input=dict): pass to provider's process_step()
           - If errors: re-show form with errors
           - If ok: merge config_data into context, advance to next step
           - If last step and detected_profiles set: go to profile selection
        """
        step_id = self._provider_steps[self._current_step_index]

        if user_input is not None:
            outcome = await self._provider.process_step(
                self.hass, step_id, user_input, self._step_context
            )

            if outcome.errors:
                step_schema = self._provider.step_schema(step_id, self._step_context)
                return self.async_show_form(
                    step_id=step_id,
                    data_schema=step_schema.schema,
                    description_placeholders=step_schema.description_placeholders,
                    errors=outcome.errors,
                )

            if outcome.config_data:
                self._step_context.update(outcome.config_data)

            if outcome.detected_profiles is not None:
                self.detected_profiles = outcome.detected_profiles

            self._current_step_index += 1
            if self._current_step_index >= len(self._provider_steps):
                return await self.async_step_profile()

            step_id = self._provider_steps[self._current_step_index]

        step_schema = self._provider.step_schema(step_id, self._step_context)
        return self.async_show_form(
            step_id=step_id,
            data_schema=step_schema.schema,
            description_placeholders=step_schema.description_placeholders,
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle profile selection."""
        if user_input is not None:
            self._step_context["profile"] = user_input["profile"]
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
            config = {
                "gateway_type": self.gateway_type,
                **self._step_context,
                **user_input,
            }
            # Clean up internal keys (prefixed with _)
            config = {k: v for k, v in config.items() if not k.startswith("_")}
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
            step_id="power",
            data_schema=POWER_SCHEMA,
            errors=errors,
        )


class HitachiYutakiOptionsFlow(config_entries.OptionsFlow):
    """Handle options as a multi-step flow mirroring initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._collected: dict[str, Any] = {}
        self._provider: GatewayConfigProvider | None = None
        self._provider_steps: list[str] = []
        self._current_step_index: int = 0
        self._step_context: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Gateway type selection."""
        if user_input is not None:
            self._collected.update(user_input)
            gateway_type = self._collected.get(
                "gateway_type", self.config_entry.data.get("gateway_type")
            )

            if gateway_type not in GATEWAY_CONFIG_PROVIDERS:
                return self.async_abort(reason="unknown_gateway")
            self._provider = GATEWAY_CONFIG_PROVIDERS[gateway_type]()
            self._provider_steps = self._provider.config_steps()
            self._current_step_index = 0
            # Pre-populate context with existing config data for defaults
            self._step_context = dict(self.config_entry.data)

            for idx, step_id in enumerate(self._provider_steps):
                setattr(
                    self,
                    f"async_step_{step_id}",
                    self._make_step_handler(idx),
                )

            return await self._handle_provider_step()

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

    def _make_step_handler(self, step_idx: int):
        """Create a step handler bound to a specific provider step index.

        HA dispatches form submissions by calling async_step_<step_id>()
        via introspection. Each handler captures its step index to ensure
        the correct provider step is processed, even if steps are called
        out of order.
        """

        async def handler(user_input=None):
            self._current_step_index = step_idx
            return await self._handle_provider_step(user_input)

        return handler

    async def _handle_provider_step(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a gateway provider configuration step.

        Same logic as the config flow handler: show form, process input,
        advance through provider steps, then go to profile selection.
        """
        step_id = self._provider_steps[self._current_step_index]

        if user_input is not None:
            outcome = await self._provider.process_step(
                self.hass, step_id, user_input, self._step_context
            )

            if outcome.errors:
                step_schema = self._provider.step_schema(step_id, self._step_context)
                return self.async_show_form(
                    step_id=step_id,
                    data_schema=step_schema.schema,
                    description_placeholders=step_schema.description_placeholders,
                    errors=outcome.errors,
                )

            if outcome.config_data:
                self._step_context.update(outcome.config_data)
            # Note: outcome.detected_profiles is intentionally not used in the
            # options flow. Profile re-selection uses the existing config entry
            # value as default, not auto-detection results.

            self._current_step_index += 1
            if self._current_step_index >= len(self._provider_steps):
                return await self.async_step_profile()

            step_id = self._provider_steps[self._current_step_index]

        step_schema = self._provider.step_schema(step_id, self._step_context)
        return self.async_show_form(
            step_id=step_id,
            data_schema=step_schema.schema,
            description_placeholders=step_schema.description_placeholders,
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
            return await self.async_step_telemetry()

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

    async def async_step_telemetry(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 5: Anonymous telemetry consent."""
        if user_input is not None:
            # Store telemetry level in options (not data — changeable without reconfig)
            telemetry_options = {
                CONF_TELEMETRY_LEVEL: user_input.get(
                    CONF_TELEMETRY_LEVEL, DEFAULT_TELEMETRY_LEVEL
                ),
            }

            # Merge: entry defaults < provider context < user-collected
            # Clean up internal keys (prefixed with _) from provider context
            provider_data = {
                k: v for k, v in self._step_context.items() if not k.startswith("_")
            }
            new_data = {**self.config_entry.data, **provider_data, **self._collected}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data, options=telemetry_options
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )
            return self.async_create_entry(title="", data={})

        current_level = self.config_entry.options.get(
            CONF_TELEMETRY_LEVEL, DEFAULT_TELEMETRY_LEVEL
        )

        return self.async_show_form(
            step_id="telemetry",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TELEMETRY_LEVEL, default=current_level
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["off", "on"],
                            translation_key="telemetry_level",
                        ),
                    ),
                }
            ),
        )
