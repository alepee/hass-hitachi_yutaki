"""DataUpdateCoordinator for Hitachi Yutaki integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_POWER_SUPPLY,
    DEFAULT_POWER_SUPPLY,
    DOMAIN,
    MASK_CIRCUIT1_COOLING,
    MASK_CIRCUIT1_HEATING,
    MASK_CIRCUIT2_COOLING,
    MASK_CIRCUIT2_HEATING,
    MASK_DHW,
    MASK_POOL,
)
from .registers import ATW_MBS_02_RegisterMap, HitachiRegisterMap

_LOGGER = logging.getLogger(__name__)


class HitachiYutakiDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Hitachi Yutaki heat pump."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.modbus_client = ModbusTcpClient(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
        )
        self.slave = entry.data[CONF_SLAVE]
        self.model = entry.data.get("unit_model")
        self.system_config = entry.data.get("system_config", 0)
        self.dev_mode = entry.data.get("dev_mode", False)
        self.power_supply = entry.data.get(CONF_POWER_SUPPLY, DEFAULT_POWER_SUPPLY)
        self.entities = []
        self.config_entry = entry

        # For now, we instantiate the map directly. This will be injected later.
        self.register_map: HitachiRegisterMap = ATW_MBS_02_RegisterMap()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=entry.data[CONF_SCAN_INTERVAL]),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Hitachi Yutaki."""
        try:
            if not self.modbus_client.connected:
                await self.hass.async_add_executor_job(self.modbus_client.connect)

            data: dict[str, Any] = {"is_available": True}

            # Preflight check
            preflight_result = await self.hass.async_add_executor_job(
                lambda addr=self.register_map.system["system_state"]: self.modbus_client.read_holding_registers(
                    address=addr,
                    count=1,
                    slave=self.slave,
                )
            )

            if preflight_result.isError():
                _LOGGER.warning(
                    "Modbus error during preflight check: %s", preflight_result
                )
                raise UpdateFailed("Modbus error during preflight check")

            system_state = preflight_result.registers[0]
            data["system_state"] = system_state

            if system_state == 1:  # Desync
                _LOGGER.warning(
                    "The gateway is out of sync with the heat pump. Check the connection."
                )
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "desync_warning",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="desync_warning",
                )
                return data

            # If we are here, system_state is 0, so we can clear any previous issue
            ir.async_delete_issue(self.hass, DOMAIN, "desync_warning")

            if system_state == 2:  # Data init
                _LOGGER.info(
                    "Hitachi Yutaki is initializing, waiting for it to be ready..."
                )
                return data

            # Read all required registers
            registers_to_read = {
                # Basic configuration registers
                **self.register_map.system,
                # Add all control registers
                **self.register_map.control_unit,
                **self.register_map.control_circuit1,
                **self.register_map.control_circuit2,
                # Add all device-specific registers
                **self.register_map.dhw,
                **self.register_map.compressor,
                **self.register_map.pool,
            }

            # If it's an S80 model, add secondary compressor registers
            if self.model == 2:  # S80
                registers_to_read.update(self.register_map.secondary_compressor)

            # Read registers in batches to optimize Modbus communication
            for register_name, register_address in registers_to_read.items():
                try:
                    result = await self.hass.async_add_executor_job(
                        lambda addr=register_address: self.modbus_client.read_holding_registers(
                            address=addr,
                            count=1,
                            slave=self.slave,
                        )
                    )

                    if result.isError():
                        _LOGGER.warning(
                            "Error reading register %s",
                            register_address,
                        )
                        raise UpdateFailed(f"Error reading register {register_address}")

                    # Update model if reading unit model register
                    if register_name == "unit_model":
                        self.model = result.registers[0]
                    # Update system configuration if reading system config register
                    elif register_name == "system_config":
                        self.system_config = result.registers[0]

                    # Store the register value
                    data[register_name] = result.registers[0]

                except ModbusException:
                    _LOGGER.warning(
                        "Modbus error reading register %s",
                        register_name,
                        exc_info=True,
                    )
                    raise

            # Update timing sensors
            for entity in self.entities:
                if hasattr(entity, "async_update_timing"):
                    await entity.async_update_timing()

            return data

        except (ModbusException, ConnectionError, OSError) as exc:
            # Set is_available to False on any error
            _LOGGER.warning("Error communicating with Hitachi Yutaki gateway: %s", exc)
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "connection_error",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="connection_error",
            )
            raise UpdateFailed("Failed to communicate with device") from exc
        finally:
            # Clear connection error issue if connection succeeds on next update
            if self.last_update_success:
                ir.async_delete_issue(self.hass, DOMAIN, "connection_error")

    async def async_write_register(self, register_key: str, value: int) -> None:
        """Write a value to a register."""
        try:
            if not self.modbus_client.connected:
                await self.hass.async_add_executor_job(self.modbus_client.connect)

            # Get the register address from control registers
            # Check all control device mappings
            register_address = None
            for device_map in [
                self.register_map.control_unit,
                self.register_map.control_circuit1,
                self.register_map.control_circuit2,
            ]:
                if register_key in device_map:
                    register_address = device_map[register_key]
                    break

            if register_address is None:
                _LOGGER.error("Unknown register key: %s", register_key)
                return

            _LOGGER.debug(
                "Writing value %s to register %s (address: %s)",
                value,
                register_key,
                register_address,
            )

            result = await self.hass.async_add_executor_job(
                lambda addr=register_address,
                val=value: self.modbus_client.write_register(
                    address=addr,
                    value=val,
                    slave=self.slave,
                )
            )

            if result.isError():
                _LOGGER.error("Error writing to register %s: %s", register_key, result)
                raise UpdateFailed(
                    f"Error writing to register {register_key}"
                ) from result

            # Trigger an immediate update to refresh values
            await self.async_request_refresh()

        except (ModbusException, ConnectionError, OSError) as error:
            _LOGGER.error("Error writing to register %s: %s", register_key, error)
            raise UpdateFailed(f"Error writing to register {register_key}") from error

    def convert_temperature(self, value: int | None) -> int | None:
        """Convert a raw temperature value."""
        if value is None:
            return None
        if value == 0xFFFF:  # Special value for sensor error
            return None
        if value > 32767:  # Handle negative values (2's complement)
            value -= 65536
        return int(value)  # Temperature is already in °C

    def convert_water_flow(self, value: int | None) -> float | None:
        """Convert a raw water flow value to m³/h."""
        if value is None:
            return None
        return float(value) / 10.0  # Convert from tenths of m³/h to m³/h

    def convert_current(self, value: int | None) -> float | None:
        """Convert a raw current value to amperes."""
        if value is None:
            return None
        return float(value) / 10.0  # Current is already in A

    def convert_pressure(self, value: int | None) -> float | None:
        """Convert a raw pressure value from MPa to bar."""
        if value is None:
            return None
        # Convert from MPa to bar (1 MPa = 10 bar)
        return float(value) / 10.0  # Value is in MPa * 100, so divide by 10 to get bar

    def is_s80_model(self) -> bool:
        """Check if the unit is an S80 model."""
        return self.model == 2

    def has_heating_circuit1(self) -> bool:
        """Check if heating circuit 1 is configured."""
        return self.dev_mode or bool(self.system_config & MASK_CIRCUIT1_HEATING)

    def has_heating_circuit2(self) -> bool:
        """Check if heating circuit 2 is configured."""
        return self.dev_mode or bool(self.system_config & MASK_CIRCUIT2_HEATING)

    def has_cooling_circuit1(self) -> bool:
        """Check if cooling circuit 1 is configured."""
        return self.dev_mode or bool(self.system_config & MASK_CIRCUIT1_COOLING)

    def has_cooling_circuit2(self) -> bool:
        """Check if cooling circuit 2 is configured."""
        return self.dev_mode or bool(self.system_config & MASK_CIRCUIT2_COOLING)

    def has_dhw(self) -> bool:
        """Check if DHW is configured."""
        return self.dev_mode or bool(self.system_config & MASK_DHW)

    def has_pool(self) -> bool:
        """Check if pool is configured."""
        return self.dev_mode or bool(self.system_config & MASK_POOL)
