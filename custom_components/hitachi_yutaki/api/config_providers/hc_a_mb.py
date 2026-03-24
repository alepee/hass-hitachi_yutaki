"""HC-A-MB gateway configuration provider.

Single-step provider that collects connection parameters (including unit_id)
and performs connectivity testing and profile detection in one step.
"""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException
import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from ...const import (
    CONF_MODBUS_DEVICE_ID,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_UNIT_ID,
    DEFAULT_DEVICE_ID,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
)
from ...profiles import PROFILES
from .. import GATEWAY_INFO, create_register_map
from . import StepOutcome, StepSchema

_LOGGER = logging.getLogger(__name__)

_STEP_CONNECTION = "hc_a_mb_connection"


class HcAMbConfigProvider:
    """Configuration provider for HC-A(16/64)MB gateways.

    This is a single-step provider. The connection step collects all
    parameters (including the HC-A-MB-specific unit_id), tests connectivity,
    reads registers, and detects the heat pump profile.
    """

    def config_steps(self) -> list[str]:
        """Return ordered list of step IDs."""
        return [_STEP_CONNECTION]

    def step_schema(self, step_id: str, context: dict[str, Any]) -> StepSchema:
        """Return the form schema for the connection step."""
        return StepSchema(
            schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_MODBUS_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_MODBUS_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Required(
                        CONF_MODBUS_DEVICE_ID, default=DEFAULT_DEVICE_ID
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): cv.positive_int,
                    vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=15)
                    ),
                }
            ),
        )

    async def process_step(
        self,
        hass: HomeAssistant,
        step_id: str,
        user_input: dict[str, Any],
        context: dict[str, Any],
    ) -> StepOutcome:
        """Process the connection step: test connectivity and detect profiles."""
        name = user_input[CONF_NAME]
        host = user_input[CONF_MODBUS_HOST]
        port = user_input[CONF_MODBUS_PORT]
        device_id = user_input[CONF_MODBUS_DEVICE_ID]
        scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        unit_id = user_input.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)

        gateway_type = "modbus_hc_a_mb"
        register_map = create_register_map(gateway_type, unit_id=unit_id)
        api_client_class = GATEWAY_INFO[gateway_type].client_class
        api_client = api_client_class(
            hass,
            name=name,
            host=host,
            port=port,
            slave=device_id,
            register_map=register_map,
        )

        try:
            if not await api_client.connect():
                return StepOutcome(errors={"base": "cannot_connect"})

            # Read base keys for profile detection
            keys_to_read = api_client.register_map.base_keys
            await api_client.read_values(keys_to_read)
            all_data = {key: await api_client.read_value(key) for key in keys_to_read}

            # Decode raw config to get boolean flags for profile detection
            decoded_data = api_client.decode_config(all_data)

            _LOGGER.debug("HC-A-MB detecting profile with data: %s", decoded_data)
            detected_profiles = [
                key for key, profile in PROFILES.items() if profile.detect(decoded_data)
            ]
            _LOGGER.debug("HC-A-MB detected profiles: %s", detected_profiles)

            if not detected_profiles:
                _LOGGER.warning(
                    "No profile detected for HC-A-MB, showing all available profiles"
                )

            return StepOutcome(
                config_data={
                    CONF_NAME: name,
                    CONF_MODBUS_HOST: host,
                    CONF_MODBUS_PORT: port,
                    CONF_MODBUS_DEVICE_ID: device_id,
                    CONF_SCAN_INTERVAL: scan_interval,
                    CONF_UNIT_ID: unit_id,
                },
                detected_profiles=detected_profiles,
            )

        except (ModbusException, ConnectionException, OSError):
            return StepOutcome(errors={"base": "cannot_connect"})
        finally:
            if api_client.connected:
                await api_client.close()
