"""Modbus client for Hitachi heat pumps."""

import logging

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from ...const import DOMAIN, get_pymodbus_device_param
from ..base import HitachiApiClient
from .registers import HitachiRegisterMap, atw_mbs_02
from .registers.atw_mbs_02 import (
    ALL_REGISTERS,
    SYSTEM_STATE_ISSUES,
    WRITABLE_KEYS,
)

_LOGGER = logging.getLogger(__name__)

# Mapping from numeric model ID to model key
MODEL_ID_TO_KEY = {
    1: "yutaki_s",
    2: "yutaki_s80",
    3: "yutaki_s_combi",
    4: "yutaki_m",
    5: "yutampo_r32",
}


class ModbusApiClient(HitachiApiClient):
    """Modbus client for Hitachi heat pumps."""

    def __init__(
        self, hass: HomeAssistant, name: str, host: str, port: int, slave: int
    ) -> None:
        """Initialize the Modbus client."""
        self._hass = hass
        self._name = name
        self._host = host
        self._port = port
        self._slave = slave
        self._client = ModbusTcpClient(host=host, port=port)
        self._lock = None
        self._data = {}
        self._unsub_updater = None
        self._register_map: HitachiRegisterMap = atw_mbs_02.AtwMbs02RegisterMap()

    @property
    def register_map(self) -> HitachiRegisterMap:
        """Return the register map for the gateway."""
        return self._register_map

    async def connect(self) -> bool:
        """Connect to the API."""
        _LOGGER.debug("Connecting to Modbus gateway at %s:%s", self._host, self._port)
        return await self._hass.async_add_executor_job(self._client.connect)

    async def close(self) -> bool:
        """Close the connection to the API."""
        _LOGGER.debug("Closing connection to Modbus gateway")
        return await self._hass.async_add_executor_job(self._client.close)

    @property
    def connected(self) -> bool:
        """Return True if the client is connected to the API."""
        return self._client.is_socket_open()

    @property
    def capabilities(self) -> dict:
        """Return the capabilities of the gateway."""
        return self._data.get("capabilities", {})

    async def get_model_key(self) -> str:
        """Return the model of the heat pump."""
        model_id = self._data.get("unit_model")
        return MODEL_ID_TO_KEY.get(model_id, "yutaki_s")

    async def read_value(self, key: str) -> int | None:
        """Read a value from the API."""
        return self._data.get(key)

    async def write_value(self, key: str, value: int) -> bool:
        """Write a value to the API."""
        if key not in WRITABLE_KEYS:
            _LOGGER.error("Unknown or non-writable register key: %s", key)
            return False

        register_address = ALL_REGISTERS[key]
        device_param = get_pymodbus_device_param()

        result = await self._hass.async_add_executor_job(
            lambda: self._client.write_register(
                address=register_address, value=value, **{device_param: self._slave}
            )
        )

        if result.isError():
            _LOGGER.error("Error writing to register %s: %s", key, result)
            return False
        return True

    async def read_values(self, keys: list[str]) -> None:
        """Fetch data from the heat pump for the given keys."""
        try:
            device_param = get_pymodbus_device_param()

            # Build a map of registers to read for this update
            registers_to_read = {
                key: ALL_REGISTERS[key] for key in keys if key in ALL_REGISTERS
            }

            # Always perform a preflight check
            preflight_result = await self._hass.async_add_executor_job(
                lambda: self._client.read_holding_registers(
                    address=ALL_REGISTERS["system_state"],
                    count=1,
                    **{device_param: self._slave},
                )
            )
            if preflight_result.isError():
                raise ModbusException("Preflight check failed")

            system_state = preflight_result.registers[0]
            self._data["system_state"] = system_state

            # Report system state issues and skip further reads
            for issue_state, issue_key in SYSTEM_STATE_ISSUES.items():
                if system_state == issue_state:
                    ir.async_create_issue(
                        self._hass,
                        DOMAIN,
                        issue_key,
                        is_fixable=False,
                        severity=ir.IssueSeverity.WARNING,
                        translation_key=issue_key,
                    )

                    _LOGGER.warning(
                        "Gateway is not ready (state: %s), skipping further reads for this cycle.",
                        system_state,
                    )
                    return
                else:
                    ir.async_delete_issue(self._hass, DOMAIN, issue_key)

            for name, address in registers_to_read.items():
                result = await self._hass.async_add_executor_job(
                    lambda addr=address: self._client.read_holding_registers(
                        address=addr, count=1, **{device_param: self._slave}
                    )
                )
                if not result.isError():
                    self._data[name] = result.registers[0]
                else:
                    _LOGGER.debug("Error reading register %s at %s", name, address)

        except ModbusException as exc:
            _LOGGER.warning("Modbus error during read_values: %s", exc)
            raise
