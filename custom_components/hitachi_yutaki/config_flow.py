"""Config flow for Hitachi Yutaki integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult, section
from homeassistant.helpers import selector

from .api import DEFAULT_GATEWAY_TYPE, GATEWAY_INFO, create_api_client
from .api.config_providers import GATEWAY_CONFIG_PROVIDERS, GatewayConfigProvider
from .const import (
    CONF_CYCLING_DETECTION,
    CONF_ELECTRICITY_PRICE_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_FLEET_PING,
    CONF_POWER_ENTITY,
    CONF_POWER_SUPPLY,
    CONF_REFRIGERANT_DETECTION,
    CONF_TELEMETRY_LEVEL,
    CONF_VOLTAGE_ENTITY,
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
    DEFAULT_CYCLING_DETECTION,
    DEFAULT_FLEET_PING,
    DEFAULT_POWER_SUPPLY,
    DEFAULT_REFRIGERANT_DETECTION,
    DEFAULT_TELEMETRY_LEVEL,
    DOMAIN,
    FLEET_PING_STATS_URL,
)
from .profiles import PROFILES

_LOGGER = logging.getLogger(__name__)

_REFRIGERANT_DOC_URL = "https://github.com/alepee/hass-hitachi_yutaki/blob/main/docs/reference/refrigerant-monitoring.md"
_PREVENTIVE_MAINTENANCE_DOC_URL = (
    "https://github.com/alepee/hass-hitachi_yutaki/blob/main/"
    "docs/reference/preventive-maintenance.md"
)
_TELEMETRY_DOC_URL = "https://github.com/alepee/hass-hitachi_yutaki/blob/main/docs/reference/telemetry.md"
_FLEET_PING_DOC_URL = f"{_TELEMETRY_DOC_URL}#fleet-ping"
SECTION_PREVENTIVE_MAINTENANCE = "preventive_maintenance"


def _preventive_maintenance_schema(
    *, refrigerant_supported: bool, refrigerant: bool, cycling: bool
) -> vol.Schema:
    """Build the beta panel schema, one toggle per preventive-maintenance detector.

    The detectors are grouped in a single section but each keeps its own
    consent: they do not share a warm-up time, a hardware scope, or a failure
    mode, so a global opt-in would switch on detections that cannot apply to
    the user's machine.
    """
    toggles: dict[Any, Any] = {}
    if refrigerant_supported:
        toggles[vol.Required(CONF_REFRIGERANT_DETECTION, default=refrigerant)] = (
            selector.BooleanSelector()
        )
    toggles[vol.Required(CONF_CYCLING_DETECTION, default=cycling)] = (
        selector.BooleanSelector()
    )
    return vol.Schema(
        {
            vol.Required(SECTION_PREVENTIVE_MAINTENANCE): section(
                vol.Schema(toggles), {"collapsed": False}
            )
        }
    )


def _flatten_preventive_maintenance(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return the section's toggles as flat option keys.

    A config-flow ``section`` nests its values under the section key, but every
    consumer reads ``options["refrigerant_detection"]`` flat. Flattening here
    keeps the storage layout independent of the presentation and avoids an
    options migration.
    """
    return dict(user_input.get(SECTION_PREVENTIVE_MAINTENANCE, {}))


# Editable optional external-sensor keys rendered by the options "sensors" step.
# These are the only keys reconciled when a selector is cleared (see #323):
# an EntitySelector left empty is omitted from user_input, so the key must be
# explicitly removed from the merged entry data rather than re-supplied from the
# existing config entry. Kept in sync with the schema built in async_step_sensors.
# They are also the only data keys a reconfigure carries over: the rest of
# entry.data is rebuilt by the gateway steps.
_OPTIONAL_SENSOR_KEYS = (
    CONF_VOLTAGE_ENTITY,
    CONF_POWER_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
    CONF_ELECTRICITY_PRICE_ENTITY,
)

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


def _power_supply_selector() -> selector.SelectSelector:
    """Single- or three-phase supply, a property of the unit's installation."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=["single", "three"],
            translation_key="power_supply",
        ),
    )


# Schema for the optional external sensors
POWER_SCHEMA = vol.Schema(
    {
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
        vol.Optional(CONF_ELECTRICITY_PRICE_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["sensor", "number", "input_number"],
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
        # Data the provider steps validated during this flow, as opposed to
        # the context, which also holds the entry's previous values as form
        # defaults when reconfiguring.
        self._validated: dict[str, Any] = {}
        self.detected_profiles: list[str] = []
        self._pending_config: dict[str, Any] = {}

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
            return await self._async_start_provider_steps(user_input["gateway_type"])

        return self.async_show_form(
            step_id="user", data_schema=GATEWAY_SELECTION_SCHEMA
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reconfigure what makes this entry this installation.

        Gateway type, connection, register map variant and heat pump model are
        changed here, with the unit's power supply, from the entry's
        "Reconfigure" menu. Settings meant to evolve (external sensors, beta
        features, telemetry) stay in the options flow.
        """
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            # Pre-populate the context so every provider step defaults to the
            # entry's current values.
            self._step_context = dict(entry.data)
            return await self._async_start_provider_steps(user_input["gateway_type"])

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                GATEWAY_SELECTION_SCHEMA,
                {"gateway_type": entry.data.get("gateway_type", DEFAULT_GATEWAY_TYPE)},
            ),
        )

    async def _async_start_provider_steps(self, gateway_type: str) -> FlowResult:
        """Bind the gateway's provider and show its first step."""
        self.gateway_type = gateway_type
        if gateway_type not in GATEWAY_CONFIG_PROVIDERS:
            return self.async_abort(reason="unknown_gateway")
        self._provider = GATEWAY_CONFIG_PROVIDERS[gateway_type]()
        self._provider_steps = self._provider.config_steps()
        self._current_step_index = 0
        self._validated = {}

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
                # Preserve user-typed values (host/port/slave/...) so the
                # user doesn't have to re-enter them on every validation
                # error. See issue #304.
                data_schema = self.add_suggested_values_to_schema(
                    step_schema.schema, user_input
                )
                return self.async_show_form(
                    step_id=step_id,
                    data_schema=data_schema,
                    description_placeholders=step_schema.description_placeholders,
                    errors=outcome.errors,
                )

            if outcome.config_data:
                self._step_context.update(outcome.config_data)
                self._validated.update(outcome.config_data)

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
        """Handle the heat pump model and its power supply.

        The power supply sits with the model: like the model, it describes the
        installed unit and is not expected to change over time.
        """
        reconfiguring = self.source == config_entries.SOURCE_RECONFIGURE
        errors: dict[str, str] = {}
        if user_input is not None:
            self._step_context["profile"] = user_input["profile"]
            self._step_context[CONF_POWER_SUPPLY] = user_input[CONF_POWER_SUPPLY]
            if not reconfiguring:
                return await self.async_step_power()
            result = self._async_finish_reconfigure()
            if isinstance(result, str):
                errors["base"] = result
            else:
                return result

        # Show all available profiles so user can manually select their machine
        profile_options = list(PROFILES.keys())
        if reconfiguring:
            # Keep the configured model by default: re-detection must not
            # silently swap a model the user picked by hand.
            default_profile = self._step_context.get("profile", vol.UNDEFINED)
        else:
            # Use first detected profile if available, otherwise use UNDEFINED
            # to force user selection
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
                ),
                vol.Required(
                    CONF_POWER_SUPPLY,
                    default=self._step_context.get(
                        CONF_POWER_SUPPLY, DEFAULT_POWER_SUPPLY
                    ),
                ): _power_supply_selector(),
            }
        )

        return self.async_show_form(
            step_id="profile", data_schema=PROFILE_SCHEMA, errors=errors
        )

    def _async_finish_reconfigure(self) -> FlowResult | str:
        """Write the reconfigured data and reload, or return a conflict error key.

        The gateway data is rebuilt from what the provider steps validated in
        this flow: a value the new reading did not return (an unreadable unit
        slot, an empty system configuration, a key of the previous gateway
        type) must not survive from the previous data. Only the settings the
        options flow owns are carried over.
        """
        entry = self._get_reconfigure_entry()
        config = {k: v for k, v in entry.data.items() if k in _OPTIONAL_SENSOR_KEYS}
        config.update(
            {k: v for k, v in self._validated.items() if not k.startswith("_")}
        )
        config["gateway_type"] = self.gateway_type
        config["profile"] = self._step_context["profile"]
        config[CONF_POWER_SUPPLY] = self._step_context[CONF_POWER_SUPPLY]

        others = [
            other.data
            for other in self._async_current_entries(include_ignore=False)
            if other.entry_id != entry.entry_id
        ]
        if any(
            data.get("gateway_type") == self.gateway_type
            and self._provider.same_unit(data, config)
            for data in others
        ):
            return self.async_abort(reason="already_configured")
        conflict = self._provider.config_conflict(config, others)
        if conflict:
            return conflict
        return self.async_update_reload_and_abort(
            entry, data=config, reload_even_if_entry_is_unchanged=False
        )

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
            description_placeholders={
                "currency": self.hass.config.currency,
            },
            errors=errors,
        )

    async def async_validate_connection(self, config: dict) -> FlowResult:
        """Validate the gateway connection through its provider."""
        errors: dict[str, str] = {}

        provider = GATEWAY_CONFIG_PROVIDERS[config["gateway_type"]]()
        api_client = create_api_client(self.hass, config)

        validation = await provider.async_validate_connection(api_client)
        if validation.error:
            errors["base"] = validation.error
        else:
            if validation.hardware_id:
                unique_id = f"{DOMAIN}_{validation.hardware_id}_{provider.unique_id_suffix(config)}"
            else:
                unique_id = provider.fallback_unique_id(config)
                _LOGGER.warning(
                    "Could not retrieve gateway hardware identifier. "
                    "Using fallback unique_id: %s. Duplicate detection will be limited.",
                    unique_id,
                )
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            conflict = provider.config_conflict(
                config,
                (
                    entry.data
                    for entry in self._async_current_entries(include_ignore=False)
                ),
            )
            if conflict:
                errors["base"] = conflict
            else:
                self._pending_config = config
                return await self.async_step_advanced_features()

        return self.async_show_form(
            step_id="power",
            data_schema=POWER_SCHEMA,
            description_placeholders={
                "currency": self.hass.config.currency,
            },
            errors=errors,
        )

    async def async_step_advanced_features(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Beta panel: one consent toggle per preventive-maintenance detector.

        Last step of the install flow, reached by every profile. The refrigerant
        toggle only appears when the profile exposes the extended compressor
        sensors; short-cycling detection is offered to all of them.
        """
        profile_cls = PROFILES.get(self._pending_config.get("profile"))
        refrigerant_supported = (
            profile_cls is not None
            and profile_cls().supports_extended_compressor_sensors
        )

        if user_input is not None:
            consents = _flatten_preventive_maintenance(user_input)
            options = {
                CONF_REFRIGERANT_DETECTION: consents.get(
                    CONF_REFRIGERANT_DETECTION, DEFAULT_REFRIGERANT_DETECTION
                ),
                CONF_CYCLING_DETECTION: consents.get(
                    CONF_CYCLING_DETECTION, DEFAULT_CYCLING_DETECTION
                ),
            }
            return self.async_create_entry(
                title=self._pending_config[CONF_NAME],
                data=self._pending_config,
                options=options,
            )

        return self.async_show_form(
            step_id="advanced_features",
            data_schema=_preventive_maintenance_schema(
                refrigerant_supported=refrigerant_supported,
                refrigerant=DEFAULT_REFRIGERANT_DETECTION,
                cycling=DEFAULT_CYCLING_DETECTION,
            ),
            description_placeholders={
                "learn_more_url": _PREVENTIVE_MAINTENANCE_DOC_URL
            },
        )


class HitachiYutakiOptionsFlow(config_entries.OptionsFlow):
    """Handle the settings meant to evolve after setup.

    External sensors, beta features and telemetry consents. The gateway, its
    connection, the heat pump model and its power supply define the entry and
    are changed through the reconfigure flow instead.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._collected: dict[str, Any] = {}
        # Whether the "sensors" step was submitted, so cleared optional sensor
        # keys are only reconciled for flows that actually reached it (#323).
        self._sensors_submitted: bool = False
        # Refrigerant consent collected by async_step_advanced_features, kept out
        # of self._collected so it never leaks into entry.data (options-only).
        self._refrigerant_detection: bool | None = None
        self._cycling_detection: bool | None = None
        # Consents collected by the telemetry and fleet ping steps. The fleet
        # ping one stays None when its step is skipped (telemetry ON).
        self._telemetry_level: str = DEFAULT_TELEMETRY_LEVEL
        self._fleet_ping: bool | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Entry point: open on the external sensors step."""
        return await self.async_step_sensors(user_input)

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: optional external sensors."""
        if user_input is not None:
            self._sensors_submitted = True
            self._collected.update(user_input)
            return await self.async_step_advanced_features()

        data = self.config_entry.data

        # Use suggested_value (not default) for the optional sensors: a default
        # is re-substituted by voluptuous when the field is omitted, so clearing
        # an EntitySelector would silently re-apply the old value. suggested_value
        # only pre-fills the field for display, leaving a cleared selector absent
        # from user_input so it can be reconciled/removed downstream (#323).
        schema_dict: dict[Any, Any] = {
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
            vol.Optional(CONF_ELECTRICITY_PRICE_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["sensor", "number", "input_number"],
                ),
            ),
        }

        # Pre-fill the optional sensor fields with the currently-configured
        # entities so the user sees their existing selection without it being
        # re-applied as a default on clear.
        suggested = {
            key: data[key] for key in _OPTIONAL_SENSOR_KEYS if data.get(key) is not None
        }

        return self.async_show_form(
            step_id="sensors",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema_dict), suggested
            ),
            description_placeholders={
                "currency": self.hass.config.currency,
            },
        )

    async def async_step_advanced_features(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options step: beta panel, one consent per preventive-maintenance detector.

        Sits just before the telemetry step and is shown for every profile: the
        refrigerant toggle is hidden when the profile has no extended
        compressor sensors (e.g. Yutampo R32), the cycling one always applies.
        """
        profile_cls = PROFILES.get(self.config_entry.data.get("profile"))
        refrigerant_supported = (
            profile_cls is not None
            and profile_cls().supports_extended_compressor_sensors
        )

        if user_input is not None:
            consents = _flatten_preventive_maintenance(user_input)
            if refrigerant_supported:
                self._refrigerant_detection = consents.get(
                    CONF_REFRIGERANT_DETECTION, DEFAULT_REFRIGERANT_DETECTION
                )
            self._cycling_detection = consents.get(
                CONF_CYCLING_DETECTION, DEFAULT_CYCLING_DETECTION
            )
            return await self.async_step_telemetry()

        return self.async_show_form(
            step_id="advanced_features",
            data_schema=_preventive_maintenance_schema(
                refrigerant_supported=refrigerant_supported,
                refrigerant=self.config_entry.options.get(
                    CONF_REFRIGERANT_DETECTION, DEFAULT_REFRIGERANT_DETECTION
                ),
                cycling=self.config_entry.options.get(
                    CONF_CYCLING_DETECTION, DEFAULT_CYCLING_DETECTION
                ),
            ),
            description_placeholders={
                "learn_more_url": _PREVENTIVE_MAINTENANCE_DOC_URL
            },
        )

    async def async_step_telemetry(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Anonymous telemetry consent."""
        if user_input is not None:
            self._telemetry_level = user_input.get(
                CONF_TELEMETRY_LEVEL, DEFAULT_TELEMETRY_LEVEL
            )
            # Telemetry ON implies the fleet ping, so its step would be moot.
            if self._telemetry_level == "on":
                return self._async_finish_options()
            return await self.async_step_fleet_ping()

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
            description_placeholders={
                "learn_more_url": _TELEMETRY_DOC_URL,
            },
        )

    async def async_step_fleet_ping(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: anonymous fleet ping, its own consent (opt-out).

        Only reached with telemetry off: telemetry ON implies the ping.
        """
        if user_input is not None:
            self._fleet_ping = user_input.get(CONF_FLEET_PING, DEFAULT_FLEET_PING)
            return self._async_finish_options()

        return self.async_show_form(
            step_id="fleet_ping",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_FLEET_PING,
                        default=self.config_entry.options.get(
                            CONF_FLEET_PING, DEFAULT_FLEET_PING
                        ),
                    ): selector.BooleanSelector(),
                }
            ),
            description_placeholders={
                "learn_more_url": _FLEET_PING_DOC_URL,
                "stats_url": FLEET_PING_STATS_URL,
            },
        )

    @callback
    def _async_finish_options(self) -> FlowResult:
        """Write the collected data and options, then reload the entry."""
        # Merge consents into existing options (preserve other options)
        new_options = {
            **self.config_entry.options,
            CONF_TELEMETRY_LEVEL: self._telemetry_level,
        }
        if self._fleet_ping is not None:
            new_options[CONF_FLEET_PING] = self._fleet_ping
        if self._refrigerant_detection is not None:
            new_options[CONF_REFRIGERANT_DETECTION] = self._refrigerant_detection
        if self._cycling_detection is not None:
            new_options[CONF_CYCLING_DETECTION] = self._cycling_detection

        new_data = {**self.config_entry.data, **self._collected}

        # Reconcile cleared optional sensors: an EntitySelector left empty is
        # omitted from user_input, so the key never lands in self._collected
        # and the merge above re-applies the old value from config_entry.data.
        # Remove any editable optional sensor key the user did not submit, so
        # a previously-configured sensor can actually be unset (#323). Only
        # the known sensor keys are touched; unrelated persisted data (host,
        # profile, capability flags, ...) is left intact.
        if self._sensors_submitted:
            for key in _OPTIONAL_SENSOR_KEYS:
                if key not in self._collected:
                    new_data.pop(key, None)

        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data, options=new_options
        )
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )
        # Return the options as the flow result so HA's OptionsFlowManager
        # persists them: returning an empty dict here makes async_finish_flow
        # overwrite entry.options with {}, wiping the telemetry and
        # refrigerant consent just written above.
        return self.async_create_entry(title="", data=new_options)
