"""API client abstraction for Hitachi Yutaki heat pumps."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import Any

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .registers import HitachiRegisterMap

_LOGGER = logging.getLogger(__name__)


class ApiError(Exception):
    """Exception raised for API-related errors."""

    pass


class HitachiYutakiApiClient(ABC):
    """Abstract API client for Hitachi Yutaki heat pumps."""

    @abstractmethod
    async def async_connect(self) -> bool:
        """Connect to the heat pump."""
        pass

    @abstractmethod
    async def async_disconnect(self) -> None:
        """Disconnect from the heat pump."""
        pass

    @abstractmethod
    async def async_get_data(self) -> dict[str, Any]:
        """Fetch all data from the heat pump."""
        pass

    @abstractmethod
    async def async_write_register(self, name: str, value: int) -> None:
        """Write a value to a register by its logical name."""
        pass

    @abstractmethod
    async def async_get_device_info(self) -> dict[str, Any]:
        """Get basic device information."""
        pass


class HitachiModbusApiClient(HitachiYutakiApiClient):
    """Modbus-specific API client for Hitachi Yutaki heat pumps."""

    def __init__(
        self,
        client: ModbusTcpClient,
        register_map: HitachiRegisterMap,
        slave: int,
        hass: Any,
    ) -> None:
        """Initialize the Modbus API client."""
        self._client = client
        self._register_map = register_map
        self._slave = slave
        self._hass = hass

    async def async_connect(self) -> bool:
        """Connect to the heat pump."""
        try:
            return await self._hass.async_add_executor_job(self._client.connect)
        except Exception as exc:
            _LOGGER.error("Failed to connect to Modbus client: %s", exc)
            raise ApiError(f"Connection failed: {exc}") from exc

    async def async_disconnect(self) -> None:
        """Disconnect from the heat pump."""
        if self._client.connected:
            self._client.close()

    async def async_get_data(self) -> dict[str, Any]:
        """Fetch all data from the heat pump."""
        try:
            if not self._client.connected:
                await self.async_connect()

            data: dict[str, Any] = {"is_available": True}

            # Preflight check
            preflight_result = await self._hass.async_add_executor_job(
                lambda addr=self._register_map.system[
                    "system_state"
                ]: self._client.read_holding_registers(
                    address=addr,
                    count=1,
                    slave=self._slave,
                )
            )

            if preflight_result.isError():
                _LOGGER.warning(
                    "Modbus error during preflight check: %s", preflight_result
                )
                raise ApiError("Modbus error during preflight check")

            system_state = preflight_result.registers[0]
            data["system_state"] = system_state

            if system_state == 1:  # Desync
                _LOGGER.warning(
                    "The gateway is out of sync with the heat pump. Check the connection."
                )
                return data

            if system_state == 2:  # Data init
                _LOGGER.info(
                    "Hitachi Yutaki is initializing, waiting for it to be ready..."
                )
                return data

            # Read all required registers
            registers_to_read = {
                # Basic configuration registers
                **self._register_map.system,
                # Add all control registers
                **self._register_map.control_unit,
                **self._register_map.control_circuit1,
                **self._register_map.control_circuit2,
                # Add all device-specific registers
                **self._register_map.dhw,
                **self._register_map.compressor,
                **self._register_map.pool,
            }

            # Read registers in batches to optimize Modbus communication
            for register_name, register_address in registers_to_read.items():
                try:
                    result = await self._hass.async_add_executor_job(
                        lambda addr=register_address: self._client.read_holding_registers(
                            address=addr,
                            count=1,
                            slave=self._slave,
                        )
                    )

                    if result.isError():
                        _LOGGER.warning(
                            "Error reading register %s",
                            register_address,
                        )
                        raise ApiError(f"Error reading register {register_address}")

                    # Store the register value
                    data[register_name] = result.registers[0]

                except ModbusException:
                    _LOGGER.warning(
                        "Modbus error reading register %s",
                        register_name,
                        exc_info=True,
                    )
                    raise

            return data

        except (ModbusException, ConnectionError, OSError) as exc:
            _LOGGER.warning("Error communicating with Hitachi Yutaki gateway: %s", exc)
            raise ApiError("Failed to communicate with device") from exc

    async def async_write_register(self, name: str, value: int) -> None:
        """Write a value to a register by its logical name."""
        try:
            if not self._client.connected:
                await self.async_connect()

            # Get the register address from control registers
            # Check all control device mappings
            register_address = None
            for device_map in [
                self._register_map.control_unit,
                self._register_map.control_circuit1,
                self._register_map.control_circuit2,
                self._register_map.dhw,
                self._register_map.pool,
            ]:
                if name in device_map:
                    register_address = device_map[name]
                    break

            if register_address is None:
                _LOGGER.error("Unknown register key: %s", name)
                raise ApiError(f"Unknown register key: {name}")

            _LOGGER.debug(
                "Writing value %s to register %s (address: %s)",
                value,
                name,
                register_address,
            )

            result = await self._hass.async_add_executor_job(
                lambda addr=register_address,
                val=value: self._client.write_register(
                    address=addr,
                    value=val,
                    slave=self._slave,
                )
            )

            if result.isError():
                _LOGGER.error("Error writing to register %s: %s", name, result)
                raise ApiError(f"Error writing to register {name}")

        except (ModbusException, ConnectionError, OSError) as error:
            _LOGGER.error("Error writing to register %s: %s", name, error)
            raise ApiError(f"Error writing to register {name}") from error

    async def async_get_device_info(self) -> dict[str, Any]:
        """Get basic device information."""
        try:
            if not self._client.connected:
                await self.async_connect()

            # Read unit model
            result = await self._hass.async_add_executor_job(
                lambda addr=self._register_map.system[
                    "unit_model"
                ]: self._client.read_holding_registers(
                    address=addr,
                    count=1,
                    slave=self._slave,
                )
            )

            if result.isError():
                raise ApiError("Failed to read unit model")

            unit_model = result.registers[0]

            # Read system configuration
            config_result = await self._hass.async_add_executor_job(
                lambda addr=self._register_map.system[
                    "system_config"
                ]: self._client.read_holding_registers(
                    address=addr,
                    count=1,
                    slave=self._slave,
                )
            )

            if config_result.isError():
                raise ApiError("Failed to read system configuration")

            system_config = config_result.registers[0]

            return {
                "unit_model": unit_model,
                "system_config": system_config,
            }

        except (ModbusException, ConnectionError, OSError) as exc:
            _LOGGER.error("Error getting device info: %s", exc)
            raise ApiError("Failed to get device info") from exc 