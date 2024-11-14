"""DataUpdateCoordinator for Hitachi Yutaki integration."""
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
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    REGISTER_CONTROL,
    REGISTER_SENSOR,
    REGISTER_R134A,
    REGISTER_UNIT_MODEL,
    REGISTER_SYSTEM_CONFIG,
    REGISTER_SYSTEM_STATUS,
)

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
        self.model = None
        self.system_config = 0

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

            data = {"is_available": True}  # Initialize with connected state

            # Read all required registers
            registers_to_read = {
                # Basic configuration registers
                "unit_model": REGISTER_UNIT_MODEL,
                "system_config": REGISTER_SYSTEM_CONFIG,
                "system_status": REGISTER_SYSTEM_STATUS,
                # Add all control registers
                **REGISTER_CONTROL,
                # Add all sensor registers
                **REGISTER_SENSOR,
            }

            # If it's an S80 model, add R134a registers
            if self.model == 2:  # S80
                registers_to_read.update(REGISTER_R134A)

            # Read registers in batches to optimize Modbus communication
            for register_name, register_address in registers_to_read.items():
                try:
                    result = await self.hass.async_add_executor_job(
                        self.modbus_client.read_holding_registers,
                        register_address,
                        1,
                        self.slave,
                    )

                    if result.isError():
                        raise UpdateFailed(f"Error reading register {register_address}")

                    # Update model if reading unit model register
                    if register_name == "unit_model":
                        self.model = result.registers[0]
                    # Update system configuration if reading system config register
                    elif register_name == "system_config":
                        self.system_config = result.registers[0]

                    # Store the register value
                    data[register_name] = result.registers[0]

                except ModbusException as error:
                    raise UpdateFailed(f"Error reading {register_name}") from error

            return data

        except Exception as error:
            # Set is_available to False on any error
            return {"is_available": False}

    async def async_write_register(self, register_key: str, value: int) -> bool:
        """Write a value to a register."""
        try:
            if not self.modbus_client.connected:
                await self.hass.async_add_executor_job(self.modbus_client.connect)

            # Get the register address from REGISTER_CONTROL
            if register_key not in REGISTER_CONTROL:
                _LOGGER.error("Unknown register key: %s", register_key)
                return False

            register_address = REGISTER_CONTROL[register_key]
            _LOGGER.debug(
                "Writing value %s to register %s (address: %s)",
                value,
                register_key,
                register_address
            )

            result = await self.hass.async_add_executor_job(
                self.modbus_client.write_register,
                register_address,
                value,
                self.slave,
            )

            if result.isError():
                _LOGGER.error("Error writing to register %s: %s", register_key, result)
                return False

            # Trigger an immediate update to refresh values
            await self.async_request_refresh()

            return True

        except ModbusException as error:
            _LOGGER.error("ModbusException writing to register %s: %s", register_key, error)
            return False
        except Exception as error:
            _LOGGER.error("Unexpected error writing to register %s: %s", register_key, error)
            return False

    def convert_temperature(self, value: int) -> float:
        """Convert a raw temperature value."""
        if value > 32767:  # Handle negative values (2's complement)
            value -= 65536
        return float(value)

    def convert_pressure(self, value: int) -> float:
        """Convert a raw pressure value to MPa."""
        return value / 100.0  # Convert from 0-510 to 0.00-5.10 MPa

    def is_s80_model(self) -> bool:
        """Check if the unit is an S80 model."""
        return self.model == 2

    def has_heating_circuit1(self) -> bool:
        """Check if heating circuit 1 is configured."""
        return bool(self.system_config & 0x0001)

    def has_heating_circuit2(self) -> bool:
        """Check if heating circuit 2 is configured."""
        return bool(self.system_config & 0x0002)

    def has_cooling_circuit1(self) -> bool:
        """Check if cooling circuit 1 is configured."""
        return bool(self.system_config & 0x0004)

    def has_cooling_circuit2(self) -> bool:
        """Check if cooling circuit 2 is configured."""
        return bool(self.system_config & 0x0008)

    def has_dhw(self) -> bool:
        """Check if DHW is configured."""
        return bool(self.system_config & 0x0010)

    def has_pool(self) -> bool:
        """Check if pool is configured."""
        return bool(self.system_config & 0x0020)
