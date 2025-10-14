"""Modbus client for Hitachi heat pumps."""

import logging
from typing import Any

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from ...const import DOMAIN, get_pymodbus_device_param
from ..base import HitachiApiClient
from .registers import HitachiRegisterMap, atw_mbs_02
from .registers.atw_mbs_02 import (
    ALL_REGISTERS,
    MASK_BOILER,
    MASK_CIRCUIT1_COOLING,
    MASK_CIRCUIT1_HEATING,
    MASK_CIRCUIT2_COOLING,
    MASK_CIRCUIT2_HEATING,
    MASK_COMPRESSOR,
    MASK_DEFROST,
    MASK_DHW,
    MASK_DHW_HEATER,
    MASK_POOL,
    MASK_PUMP1,
    MASK_PUMP2,
    MASK_PUMP3,
    MASK_SMART_FUNCTION,
    MASK_SOLAR,
    MASK_SPACE_HEATER,
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

        register_address = ALL_REGISTERS[key].address
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

    @property
    def has_dhw(self) -> bool:
        """Return True if DHW is configured."""
        system_config = self._data.get("system_config", 0)
        return bool(system_config & MASK_DHW)

    @property
    def has_circuit1_heating(self) -> bool:
        """Return True if heating for circuit 1 is configured."""
        system_config = self._data.get("system_config", 0)
        return bool(system_config & MASK_CIRCUIT1_HEATING)

    @property
    def has_circuit1_cooling(self) -> bool:
        """Return True if cooling for circuit 1 is configured."""
        system_config = self._data.get("system_config", 0)
        return bool(system_config & MASK_CIRCUIT1_COOLING)

    @property
    def has_circuit2_heating(self) -> bool:
        """Return True if heating for circuit 2 is configured."""
        system_config = self._data.get("system_config", 0)
        return bool(system_config & MASK_CIRCUIT2_HEATING)

    @property
    def has_circuit2_cooling(self) -> bool:
        """Return True if cooling for circuit 2 is configured."""
        system_config = self._data.get("system_config", 0)
        return bool(system_config & MASK_CIRCUIT2_COOLING)

    @property
    def has_pool(self) -> bool:
        """Return True if pool heating is configured."""
        system_config = self._data.get("system_config", 0)
        return bool(system_config & MASK_POOL)

    def decode_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """Decode raw config data into a dictionary of boolean flags."""
        system_config = data.get("system_config", 0)
        decoded = data.copy()
        decoded["has_dhw"] = bool(system_config & MASK_DHW)
        decoded["has_circuit1_heating"] = bool(system_config & MASK_CIRCUIT1_HEATING)
        decoded["has_circuit1_cooling"] = bool(system_config & MASK_CIRCUIT1_COOLING)
        decoded["has_circuit2_heating"] = bool(system_config & MASK_CIRCUIT2_HEATING)
        decoded["has_circuit2_cooling"] = bool(system_config & MASK_CIRCUIT2_COOLING)
        decoded["has_pool"] = bool(system_config & MASK_POOL)
        return decoded

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
                    address=ALL_REGISTERS["system_state"].address,
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

            for name, definition in registers_to_read.items():
                result = await self._hass.async_add_executor_job(
                    lambda addr=definition.address: self._client.read_holding_registers(
                        address=addr, count=1, **{device_param: self._slave}
                    )
                )
                if not result.isError():
                    value = result.registers[0]
                    if definition.deserializer:
                        self._data[name] = definition.deserializer(value)
                    else:
                        self._data[name] = value
                else:
                    _LOGGER.debug(
                        "Error reading register %s at %s", name, definition.address
                    )

        except ModbusException as exc:
            _LOGGER.warning("Modbus error during read_values: %s", exc)
            raise

    @property
    def is_defrosting(self) -> bool:
        """Return True if the unit is in defrost mode."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & MASK_DEFROST)

    @property
    def is_solar_active(self) -> bool:
        """Return True if solar system is active."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & MASK_SOLAR)

    @property
    def is_pump1_running(self) -> bool:
        """Return True if pump 1 is running."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & MASK_PUMP1)

    @property
    def is_pump2_running(self) -> bool:
        """Return True if pump 2 is running."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & MASK_PUMP2)

    @property
    def is_pump3_running(self) -> bool:
        """Return True if pump 3 is running."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & MASK_PUMP3)

    @property
    def is_compressor_running(self) -> bool:
        """Return True if compressor is running."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & MASK_COMPRESSOR)

    @property
    def is_boiler_active(self) -> bool:
        """Return True if backup boiler is active."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & MASK_BOILER)

    @property
    def is_dhw_heater_active(self) -> bool:
        """Return True if DHW electric heater is active."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & MASK_DHW_HEATER)

    @property
    def is_space_heater_active(self) -> bool:
        """Return True if space heating electric heater is active."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & MASK_SPACE_HEATER)

    @property
    def is_smart_function_active(self) -> bool:
        """Return True if smart grid function is active."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & MASK_SMART_FUNCTION)
