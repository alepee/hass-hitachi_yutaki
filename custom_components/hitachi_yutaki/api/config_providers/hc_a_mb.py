"""HC-A-MB gateway configuration provider.

Single-step provider that collects connection parameters (including unit_id)
and performs connectivity testing and profile detection in one step.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException
import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from ...const import (
    CONF_INDOOR_ADDRESS,
    CONF_MODBUS_DEVICE_ID,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_OUTDOOR_CYCLE,
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
from ..base import ReadResult
from . import StepOutcome, StepSchema
from .modbus import ModbusConfigProvider

_LOGGER = logging.getLogger(__name__)

_STEP_CONNECTION = "hc_a_mb_connection"


class HcAMbConfigProvider(ModbusConfigProvider):
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
        if step_id != _STEP_CONNECTION:
            msg = f"Unknown step_id: {step_id}"
            raise ValueError(msg)
        return StepSchema(
            schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME, default=context.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(
                        CONF_MODBUS_HOST,
                        default=context.get(CONF_MODBUS_HOST, DEFAULT_HOST),
                    ): str,
                    vol.Required(
                        CONF_MODBUS_PORT,
                        default=context.get(CONF_MODBUS_PORT, DEFAULT_PORT),
                    ): cv.port,
                    vol.Required(
                        CONF_MODBUS_DEVICE_ID,
                        default=context.get(CONF_MODBUS_DEVICE_ID, DEFAULT_DEVICE_ID),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=context.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): cv.positive_int,
                    vol.Required(
                        CONF_UNIT_ID, default=context.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=15)),
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
        if step_id != _STEP_CONNECTION:
            msg = f"Unknown step_id: {step_id}"
            raise ValueError(msg)
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
            keys_to_read = api_client.base_keys
            result = await api_client.read_values(keys_to_read)
            if result == ReadResult.GATEWAY_NOT_READY:
                # _data is not populated; trying to decode would yield None
                # values and crash. Surface a user-facing error instead.
                return StepOutcome(errors={"base": "gateway_not_ready"})
            all_data = {key: await api_client.read_value(key) for key in keys_to_read}

            # Decode raw config to get boolean flags for profile detection
            decoded_data = api_client.decode_config(all_data)
            system_config = int(all_data.get("system_config") or 0)

            # Read the unit's (Ou, Iu) identity from the gateway unit table.
            # Ou keys the outdoor register block on multi-system gateways
            # (#353); the pair identifies the unit across slot moves (#476).
            slots = await api_client.async_read_unit_table(unit_id, 1)
            unit_slot = slots[0] if slots and slots[0].is_valid else None

            _LOGGER.debug("HC-A-MB detecting profile with data: %s", decoded_data)
            detected_profiles = [
                key for key, profile in PROFILES.items() if profile.detect(decoded_data)
            ]
            _LOGGER.debug("HC-A-MB detected profiles: %s", detected_profiles)

            if not detected_profiles:
                _LOGGER.warning(
                    "No profile detected for HC-A-MB, showing all available profiles"
                )

            # Persist system_config so COP services and device capabilities
            # can be initialised on next setup before any refresh (#308).
            config_data: dict[str, Any] = {
                CONF_NAME: name,
                CONF_MODBUS_HOST: host,
                CONF_MODBUS_PORT: port,
                CONF_MODBUS_DEVICE_ID: device_id,
                CONF_SCAN_INTERVAL: scan_interval,
                CONF_UNIT_ID: unit_id,
            }
            if system_config:
                config_data["system_config"] = system_config
            if unit_slot is not None:
                config_data[CONF_OUTDOOR_CYCLE] = unit_slot.outdoor_cycle
                config_data[CONF_INDOOR_ADDRESS] = unit_slot.indoor_address

            return StepOutcome(
                config_data=config_data,
                detected_profiles=detected_profiles,
            )

        except (ModbusException, ConnectionException, OSError):
            return StepOutcome(errors={"base": "cannot_connect"})
        finally:
            if api_client.connected:
                await api_client.close()

    # ------------------------------------------------------------------
    # Config entry rules
    # ------------------------------------------------------------------

    def unique_id_suffix(self, config: Mapping[str, Any]) -> str:
        """Return the unit's ``(Ou, Iu)`` pair, or its slot when unknown (#476).

        The slot moves when the gateway renumbers its units, so a slot suffix
        let an entry whose unit had moved block a new unit added on its old
        slot. Entries created before #476 keep their slot suffix (their
        ``unique_id`` is never rewritten, so their telemetry ``device_hash`` is
        preserved); both formats cannot collide.
        """
        identity = self.unit_identity(config)
        if identity is not None:
            return f"c{identity[0]}_i{identity[1]}"
        return str(config.get(CONF_UNIT_ID, DEFAULT_UNIT_ID))

    def config_conflict(
        self, config: Mapping[str, Any], entries: Iterable[Mapping[str, Any]]
    ) -> str | None:
        """Refuse a second entry on an outdoor cycle already in use (#404).

        The outdoor register block is keyed on the refrigerant cycle, not on
        the slot. Two entries resolving to the same cycle read and drive the
        same outdoor unit, which silently corrupts the first unit's data.
        """
        outdoor_cycle = config.get(CONF_OUTDOOR_CYCLE)
        if outdoor_cycle is None:
            return None
        if any(
            data.get(CONF_OUTDOOR_CYCLE) == outdoor_cycle
            and data.get(CONF_MODBUS_HOST) == config[CONF_MODBUS_HOST]
            and data.get(CONF_MODBUS_PORT) == config[CONF_MODBUS_PORT]
            for data in entries
        ):
            return "outdoor_cycle_in_use"
        return None

    def unit_identity(self, data: Mapping[str, Any]) -> tuple | None:
        """Return the unit's ``(Ou, Iu)`` pair, None if not recorded yet."""
        outdoor_cycle = data.get(CONF_OUTDOOR_CYCLE)
        indoor_address = data.get(CONF_INDOOR_ADDRESS)
        if outdoor_cycle is None or indoor_address is None:
            return None
        return (outdoor_cycle, indoor_address)

    def diagnostics(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Return which unit the entry is bound to and its current slot (#476)."""
        return {
            "slot": data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
            "outdoor_cycle": data.get(CONF_OUTDOOR_CYCLE),
            "indoor_address": data.get(CONF_INDOOR_ADDRESS),
        }
