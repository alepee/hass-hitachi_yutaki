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
    HVAC_UNIT_MODE_AUTO,
    HVAC_UNIT_MODE_COOL,
    HVAC_UNIT_MODE_HEAT,
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

    async def _trigger_refresh(self) -> None:
        """Trigger a refresh of coordinator data after a write operation."""
        # Note: Refresh is handled by coordinator.async_request_refresh() in entities
        return

    # Unit control - Getters
    def get_unit_power(self) -> bool | None:
        """Get the main unit power state."""
        value = self._data.get("unit_power")
        if value is None:
            return None
        return bool(value)

    def get_unit_mode(self):
        """Get the current unit mode."""
        from homeassistant.components.climate import HVACMode

        unit_mode = self._data.get("unit_mode")
        if unit_mode is None:
            return None
        return {
            HVAC_UNIT_MODE_COOL: HVACMode.COOL,
            HVAC_UNIT_MODE_HEAT: HVACMode.HEAT,
            HVAC_UNIT_MODE_AUTO: HVACMode.AUTO,
        }.get(unit_mode)

    # Unit control - Setters
    async def set_unit_power(self, enabled: bool) -> bool:
        """Enable/disable the main heat pump unit."""
        return await self.write_value("unit_power", 1 if enabled else 0)

    async def set_unit_mode(self, mode) -> bool:
        """Set the unit operation mode."""
        from homeassistant.components.climate import HVACMode

        mode_map = {
            HVACMode.COOL: HVAC_UNIT_MODE_COOL,
            HVACMode.HEAT: HVAC_UNIT_MODE_HEAT,
            HVACMode.AUTO: HVAC_UNIT_MODE_AUTO,
        }
        unit_mode = mode_map.get(mode)
        if unit_mode is None:
            return False
        return await self.write_value("unit_mode", unit_mode)

    # Circuit control - Getters
    def get_circuit_power(self, circuit_id: int) -> bool | None:
        """Get circuit power state."""
        key = f"circuit{circuit_id}_power"
        value = self._data.get(key)
        if value is None:
            return None
        return bool(value)

    def get_circuit_current_temperature(self, circuit_id: int) -> float | None:
        """Get current temperature for a circuit (already deserialized by register)."""
        key = f"circuit{circuit_id}_current_temp"
        temp = self._data.get(key)
        if temp is None:
            return None
        return float(temp)

    def get_circuit_target_temperature(self, circuit_id: int) -> float | None:
        """Get target temperature for a circuit (already deserialized by register)."""
        key = f"circuit{circuit_id}_target_temp"
        temp = self._data.get(key)
        if temp is None:
            return None
        return float(temp)

    def get_circuit_eco_mode(self, circuit_id: int) -> bool | None:
        """Get ECO mode state for a circuit (True=ECO, False=COMFORT)."""
        key = f"circuit{circuit_id}_eco_mode"
        value = self._data.get(key)
        if value is None:
            return None
        # Note: eco_mode uses inverted logic (0=eco, 1=comfort)
        return value == 0

    def get_circuit_thermostat(self, circuit_id: int) -> bool | None:
        """Get Modbus thermostat state for a circuit."""
        key = f"circuit{circuit_id}_thermostat"
        value = self._data.get(key)
        if value is None:
            return None
        return bool(value)

    def get_circuit_otc_method_heating(self, circuit_id: int) -> int | None:
        """Get OTC calculation method for heating."""
        key = f"circuit{circuit_id}_otc_calculation_method_heating"
        return self._data.get(key)

    def get_circuit_otc_method_cooling(self, circuit_id: int) -> int | None:
        """Get OTC calculation method for cooling."""
        key = f"circuit{circuit_id}_otc_calculation_method_cooling"
        return self._data.get(key)

    def get_circuit_max_flow_temp_heating(self, circuit_id: int) -> float | None:
        """Get maximum heating water temperature for OTC (in °C)."""
        key = f"circuit{circuit_id}_max_flow_temp_heating_otc"
        value = self._data.get(key)
        if value is None:
            return None
        return float(value)

    def get_circuit_max_flow_temp_cooling(self, circuit_id: int) -> float | None:
        """Get maximum cooling water temperature for OTC (in °C)."""
        key = f"circuit{circuit_id}_max_flow_temp_cooling_otc"
        value = self._data.get(key)
        if value is None:
            return None
        return float(value)

    def get_circuit_heat_eco_offset(self, circuit_id: int) -> int | None:
        """Get temperature offset for ECO heating mode (in °C)."""
        key = f"circuit{circuit_id}_heat_eco_offset"
        return self._data.get(key)

    def get_circuit_cool_eco_offset(self, circuit_id: int) -> int | None:
        """Get temperature offset for ECO cooling mode (in °C)."""
        key = f"circuit{circuit_id}_cool_eco_offset"
        return self._data.get(key)

    # Circuit control - Setters
    async def set_circuit_power(self, circuit_id: int, enabled: bool) -> bool:
        """Enable/disable a heating/cooling circuit."""
        key = f"circuit{circuit_id}_power"
        return await self.write_value(key, 1 if enabled else 0)

    async def set_circuit_target_temperature(
        self, circuit_id: int, temperature: float
    ) -> bool:
        """Set target temperature for a circuit."""
        key = f"circuit{circuit_id}_target_temp"
        value = int(temperature * 10)
        return await self.write_value(key, value)

    async def set_circuit_eco_mode(self, circuit_id: int, enabled: bool) -> bool:
        """Enable/disable ECO mode for a circuit."""
        key = f"circuit{circuit_id}_eco_mode"
        # Note: eco_mode uses inverted logic (0=eco, 1=comfort)
        value = 0 if enabled else 1
        return await self.write_value(key, value)

    async def set_circuit_thermostat(self, circuit_id: int, enabled: bool) -> bool:
        """Enable/disable Modbus thermostat for a circuit."""
        key = f"circuit{circuit_id}_thermostat"
        return await self.write_value(key, 1 if enabled else 0)

    async def set_circuit_otc_method_heating(
        self, circuit_id: int, method: int
    ) -> bool:
        """Set OTC calculation method for heating."""
        key = f"circuit{circuit_id}_otc_calculation_method_heating"
        return await self.write_value(key, method)

    async def set_circuit_otc_method_cooling(
        self, circuit_id: int, method: int
    ) -> bool:
        """Set OTC calculation method for cooling."""
        key = f"circuit{circuit_id}_otc_calculation_method_cooling"
        return await self.write_value(key, method)

    async def set_circuit_max_flow_temp_heating(
        self, circuit_id: int, temperature: float
    ) -> bool:
        """Set maximum heating water temperature for OTC (stored in tenths of degrees)."""
        key = f"circuit{circuit_id}_max_flow_temp_heating_otc"
        return await self.write_value(key, int(temperature * 10))

    async def set_circuit_max_flow_temp_cooling(
        self, circuit_id: int, temperature: float
    ) -> bool:
        """Set maximum cooling water temperature for OTC (stored in tenths of degrees)."""
        key = f"circuit{circuit_id}_max_flow_temp_cooling_otc"
        return await self.write_value(key, int(temperature * 10))

    async def set_circuit_heat_eco_offset(self, circuit_id: int, offset: int) -> bool:
        """Set temperature offset for ECO heating mode."""
        key = f"circuit{circuit_id}_heat_eco_offset"
        return await self.write_value(key, offset)

    async def set_circuit_cool_eco_offset(self, circuit_id: int, offset: int) -> bool:
        """Set temperature offset for ECO cooling mode."""
        key = f"circuit{circuit_id}_cool_eco_offset"
        return await self.write_value(key, offset)

    # DHW control - Getters
    def get_dhw_power(self) -> bool | None:
        """Get DHW power state."""
        value = self._data.get("dhw_power")
        if value is None:
            return None
        return bool(value)

    def get_dhw_current_temperature(self) -> float | None:
        """Get current DHW temperature (already deserialized by register)."""
        temp = self._data.get("dhw_current_temp")
        if temp is None:
            return None
        return float(temp)

    def get_dhw_target_temperature(self) -> float | None:
        """Get DHW target temperature."""
        temp = self._data.get("dhw_target_temp")
        if temp is None:
            return None
        return float(temp)

    def get_dhw_high_demand(self) -> bool | None:
        """Get DHW high demand mode state."""
        value = self._data.get("dhw_high_demand")
        if value is None:
            return None
        return bool(value)

    def get_dhw_boost(self) -> bool | None:
        """Get DHW boost mode state."""
        value = self._data.get("dhw_boost")
        if value is None:
            return None
        return bool(value)

    def get_dhw_antilegionella_temperature(self) -> float | None:
        """Get anti-legionella target temperature."""
        temp = self._data.get("dhw_antilegionella_temp")
        if temp is None:
            return None
        return float(temp)

    # DHW control - Setters
    async def set_dhw_power(self, enabled: bool) -> bool:
        """Enable/disable domestic hot water production."""
        return await self.write_value("dhw_power", 1 if enabled else 0)

    async def set_dhw_target_temperature(self, temperature: float) -> bool:
        """Set DHW target temperature (stored in tenths of degrees)."""
        return await self.write_value("dhw_target_temp", int(temperature * 10))

    async def set_dhw_high_demand(self, enabled: bool) -> bool:
        """Enable/disable DHW high demand mode."""
        return await self.write_value("dhw_high_demand", 1 if enabled else 0)

    async def set_dhw_boost(self, enabled: bool) -> bool:
        """Enable/disable DHW boost mode."""
        return await self.write_value("dhw_boost", 1 if enabled else 0)

    async def start_dhw_antilegionella(self) -> bool:
        """Start anti-legionella treatment cycle."""
        return await self.write_value("dhw_antilegionella", 1)

    async def set_dhw_antilegionella_temperature(self, temperature: float) -> bool:
        """Set anti-legionella target temperature (stored in tenths of degrees)."""
        return await self.write_value("dhw_antilegionella_temp", int(temperature * 10))

    # Pool control - Getters
    def get_pool_power(self) -> bool | None:
        """Get pool heating power state."""
        value = self._data.get("pool_power")
        if value is None:
            return None
        return bool(value)

    def get_pool_current_temperature(self) -> float | None:
        """Get current pool temperature (already deserialized by register)."""
        temp = self._data.get("pool_current_temp")
        if temp is None:
            return None
        return float(temp)

    def get_pool_target_temperature(self) -> float | None:
        """Get pool target temperature."""
        temp = self._data.get("pool_target_temp")
        if temp is None:
            return None
        return float(temp)

    # Pool control - Setters
    async def set_pool_power(self, enabled: bool) -> bool:
        """Enable/disable pool heating."""
        return await self.write_value("pool_power", 1 if enabled else 0)

    async def set_pool_target_temperature(self, temperature: float) -> bool:
        """Set pool target temperature (stored in tenths of degrees)."""
        return await self.write_value("pool_target_temp", int(temperature * 10))
