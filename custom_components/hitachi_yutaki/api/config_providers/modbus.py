"""Shared Modbus configuration rules, hidden from integration callers."""

from collections.abc import Mapping
import logging
from typing import Any

from pymodbus.exceptions import ModbusException

from ...const import CONF_MODBUS_DEVICE_ID, CONF_MODBUS_HOST, CONF_MODBUS_PORT
from ..base import HitachiApiClient, ReadResult
from . import ConnectionValidation

_LOGGER = logging.getLogger(__name__)


class ModbusConfigProvider:
    """Common transport-specific rules for Modbus gateway providers."""

    async def async_validate_connection(
        self, client: HitachiApiClient
    ) -> ConnectionValidation:
        """Validate the connection without exposing transport details to the flow."""
        try:
            if not await client.connect():
                return ConnectionValidation(error="cannot_connect")
            result = await client.read_values(client.gateway_keys)
            if result is ReadResult.GATEWAY_NOT_READY:
                state = await client.read_value("system_state")
                error = {
                    "initializing": "system_initializing",
                    "desynchronized": "desync_error",
                }.get(state, "cannot_connect")
                return ConnectionValidation(error=error)
            if not await client.get_model_key():
                return ConnectionValidation(error="invalid_slave")
            return ConnectionValidation(hardware_id=await client.async_get_unique_id())
        except (ModbusException, OSError):
            return ConnectionValidation(error="cannot_connect")
        finally:
            if client.connected:
                try:
                    await client.close()
                except (ModbusException, OSError):
                    _LOGGER.debug("Error closing validation connection", exc_info=True)

    def unique_id_suffix(self, config: Mapping[str, Any]) -> str:
        """Return the per-unit identity supplied by each concrete provider."""
        raise NotImplementedError

    def fallback_unique_id(self, config: Mapping[str, Any]) -> str:
        """Preserve the exact host/device/unit fallback used by existing entries."""
        return (
            f"{config[CONF_MODBUS_HOST]}_{config[CONF_MODBUS_DEVICE_ID]}_"
            f"{self.unique_id_suffix(config)}"
        )

    def configuration_url(self, config: Mapping[str, Any]) -> str | None:
        """Return the gateway's web administration URL."""
        return f"http://{config[CONF_MODBUS_HOST]}"

    @property
    def sensitive_config_keys(self) -> set[str]:
        """Return Modbus connection details to redact from diagnostics."""
        return {CONF_MODBUS_HOST}

    def same_gateway(self, first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
        """Compare the network endpoints of two Modbus gateways."""
        return first.get(CONF_MODBUS_HOST) == second.get(
            CONF_MODBUS_HOST
        ) and first.get(CONF_MODBUS_PORT) == second.get(CONF_MODBUS_PORT)
