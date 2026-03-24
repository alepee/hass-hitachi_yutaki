"""ATW-MBS-02 gateway configuration provider.

Extracts ATW-MBS-02-specific connection testing, variant auto-detection,
and profile detection from config_flow.py into a GatewayConfigProvider.
"""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException
import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from ...const import (
    CONF_MODBUS_DEVICE_ID,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    DEFAULT_DEVICE_ID,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
)
from ...profiles import PROFILES
from .. import GATEWAY_INFO, create_register_map
from ..modbus.registers import GATEWAY_VARIANTS
from . import StepOutcome, StepSchema

_LOGGER = logging.getLogger(__name__)

_GATEWAY_TYPE = "modbus_atw_mbs_02"
_MODEL_DECODER_URL = (
    "https://alepee.github.io/hass-hitachi_yutaki/tools/model-decoder.html"
)


class AtwMbs02ConfigProvider:
    """Configuration provider for the ATW-MBS-02 gateway."""

    def config_steps(self) -> list[str]:
        """Return ordered list of step IDs."""
        return ["atw_mbs_02_connection", "atw_mbs_02_variant"]

    def step_schema(self, step_id: str, context: dict[str, Any]) -> StepSchema:
        """Return the form schema and description placeholders for a step."""
        if step_id == "atw_mbs_02_connection":
            return self._connection_schema()
        if step_id == "atw_mbs_02_variant":
            return self._variant_schema(context)
        msg = f"Unknown step_id: {step_id}"
        raise ValueError(msg)

    async def process_step(
        self,
        hass: HomeAssistant,
        step_id: str,
        user_input: dict[str, Any],
        context: dict[str, Any],
    ) -> StepOutcome:
        """Process user input for a step."""
        if step_id == "atw_mbs_02_connection":
            return await self._process_connection(hass, user_input)
        if step_id == "atw_mbs_02_variant":
            return await self._process_variant(hass, user_input, context)
        msg = f"Unknown step_id: {step_id}"
        raise ValueError(msg)

    # ------------------------------------------------------------------
    # Connection step
    # ------------------------------------------------------------------

    @staticmethod
    def _connection_schema() -> StepSchema:
        """Build schema for the connection step."""
        schema = vol.Schema(
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
        return StepSchema(schema=schema)

    async def _process_connection(
        self,
        hass: HomeAssistant,
        user_input: dict[str, Any],
    ) -> StepOutcome:
        """Test Modbus connectivity and auto-detect variant."""
        config = {
            CONF_NAME: user_input[CONF_NAME],
            CONF_MODBUS_HOST: user_input[CONF_MODBUS_HOST],
            CONF_MODBUS_PORT: user_input[CONF_MODBUS_PORT],
            CONF_MODBUS_DEVICE_ID: user_input[CONF_MODBUS_DEVICE_ID],
            CONF_SCAN_INTERVAL: user_input.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
        }

        # Test basic connectivity
        if not await self._test_connection(hass, config):
            return StepOutcome(errors={"base": "cannot_connect"})

        # Auto-detect variant for the next step
        detected_variant = await self._detect_variant(hass, config)
        config["_detected_variant"] = detected_variant or ""

        return StepOutcome(config_data=config)

    # ------------------------------------------------------------------
    # Variant step
    # ------------------------------------------------------------------

    @staticmethod
    def _variant_schema(context: dict[str, Any]) -> StepSchema:
        """Build schema for the variant selection step."""
        detected_variant = context.get("_detected_variant", "")
        variant_keys = list(GATEWAY_VARIANTS[_GATEWAY_TYPE].keys())
        default_variant = detected_variant if detected_variant else vol.UNDEFINED

        if detected_variant:
            auto_detect_status = detected_variant.upper().replace("GEN", "Gen ")
        else:
            auto_detect_status = "?"

        schema = vol.Schema(
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
        )
        return StepSchema(
            schema=schema,
            description_placeholders={
                "model_decoder_url": _MODEL_DECODER_URL,
                "detected_variant": auto_detect_status,
            },
        )

    async def _process_variant(
        self,
        hass: HomeAssistant,
        user_input: dict[str, Any],
        context: dict[str, Any],
    ) -> StepOutcome:
        """Detect profiles using the chosen variant."""
        variant = user_input["gateway_variant"]

        detected_profiles, error = await self._detect_profiles(hass, context, variant)
        if error:
            return StepOutcome(errors={"base": error})

        return StepOutcome(
            config_data={"gateway_variant": variant},
            detected_profiles=detected_profiles,
        )

    # ------------------------------------------------------------------
    # Modbus helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _test_connection(
        hass: HomeAssistant,
        config: dict[str, Any],
    ) -> bool:
        """Test basic Modbus connectivity.

        Uses the default (gen2) register map for the connectivity test —
        only connect + read gateway_keys to verify the gateway is reachable.
        """
        api_client_class = GATEWAY_INFO[_GATEWAY_TYPE].client_class
        register_map = create_register_map(
            _GATEWAY_TYPE, DEFAULT_UNIT_ID, gateway_variant=None
        )
        api_client = api_client_class(
            hass,
            name=config[CONF_NAME],
            host=config[CONF_MODBUS_HOST],
            port=config[CONF_MODBUS_PORT],
            slave=config[CONF_MODBUS_DEVICE_ID],
            register_map=register_map,
        )
        try:
            if not await api_client.connect():
                return False
            await api_client.read_values(api_client.register_map.gateway_keys)
            return True
        except (ModbusException, ConnectionException, OSError):
            return False
        finally:
            if api_client.connected:
                await api_client.close()

    @staticmethod
    async def _detect_variant(
        hass: HomeAssistant,
        config: dict[str, Any],
    ) -> str | None:
        """Auto-detect the gateway variant by probing with each register map.

        Tries gen2 first (more common), then gen1. Returns the variant key
        if unit_model reads back a known value, otherwise None.
        """
        variants = GATEWAY_VARIANTS.get(_GATEWAY_TYPE, {})
        if not variants:
            return None

        api_client_class = GATEWAY_INFO[_GATEWAY_TYPE].client_class

        for variant_key in ["gen2", "gen1"]:
            if variant_key not in variants:
                continue
            register_map = create_register_map(
                _GATEWAY_TYPE, DEFAULT_UNIT_ID, gateway_variant=variant_key
            )
            api_client = api_client_class(
                hass,
                name="variant_probe",
                host=config[CONF_MODBUS_HOST],
                port=config[CONF_MODBUS_PORT],
                slave=config[CONF_MODBUS_DEVICE_ID],
                register_map=register_map,
            )
            try:
                if not await api_client.connect():
                    return None
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
                _LOGGER.debug("Variant probe failed for %s", variant_key)
            finally:
                if api_client.connected:
                    await api_client.close()

        return None

    @staticmethod
    async def _detect_profiles(
        hass: HomeAssistant,
        context: dict[str, Any],
        variant: str,
    ) -> tuple[list[str], str | None]:
        """Connect, read base_keys, decode config, and detect profiles.

        Returns (detected_profiles, error_key). error_key is None on success.
        """
        api_client_class = GATEWAY_INFO[_GATEWAY_TYPE].client_class
        register_map = create_register_map(
            _GATEWAY_TYPE, DEFAULT_UNIT_ID, gateway_variant=variant
        )
        api_client = api_client_class(
            hass,
            name=context[CONF_NAME],
            host=context[CONF_MODBUS_HOST],
            port=context[CONF_MODBUS_PORT],
            slave=context[CONF_MODBUS_DEVICE_ID],
            register_map=register_map,
        )
        try:
            if not await api_client.connect():
                return [], "cannot_connect"

            _LOGGER.debug("Fetching all values to allow profiles to detect device")
            keys_to_read = api_client.register_map.base_keys
            await api_client.read_values(keys_to_read)
            all_data = {key: await api_client.read_value(key) for key in keys_to_read}

            decoded_data = api_client.decode_config(all_data)

            _LOGGER.debug("Detecting profile with data: %s", decoded_data)
            detected_profiles = [
                key for key, profile in PROFILES.items() if profile.detect(decoded_data)
            ]

            _LOGGER.debug("Detected profiles: %s", detected_profiles)
            if not detected_profiles:
                _LOGGER.warning("No profile detected, showing all available profiles")
            return detected_profiles, None
        except (ModbusException, ConnectionException, OSError):
            return [], "cannot_connect"
        finally:
            if api_client.connected:
                await api_client.close()
