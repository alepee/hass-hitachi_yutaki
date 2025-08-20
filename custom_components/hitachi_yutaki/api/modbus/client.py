"""PyModbus compatibility shim for device addressing across versions.

This module provides a unified interface for PyModbus client operations,
handling the transition from 'slave' to 'device_id' parameter between
versions 3.9.2 and 3.11.1+.
"""

from __future__ import annotations

import inspect
from typing import Any

from pymodbus.client import ModbusTcpClient


class ModbusClientShim:
    """Compatibility wrapper for PyModbus client addressing parameters.

    Handles the transition from 'slave' (3.9.2 and earlier) to 'device_id' (3.11.1+)
    while maintaining a consistent interface.
    """

    def __init__(self, host: str, port: int):
        """Initialize the underlying ModbusTcpClient and detect parameter names."""
        self._client = ModbusTcpClient(host=host, port=port)
        self._device_kw = self._detect_device_parameter()

    def _detect_device_parameter(self) -> str:
        """Detect the correct parameter name for device addressing.

        Returns 'device_id' for PyModbus 3.11.1+, 'slave' for 3.9.2 and earlier.
        """
        try:
            sig = inspect.signature(self._client.read_holding_registers)
            if "device_id" in sig.parameters:
                return "device_id"
            if "slave" in sig.parameters:
                return "slave"
            if "unit" in sig.parameters:
                return "unit"
        except Exception:
            pass
        # Default to device_id for future compatibility
        return "device_id"

    def connect(self) -> bool:
        """Connect to the Modbus device."""
        return self._client.connect()

    def close(self) -> None:
        """Close the connection."""
        self._client.close()

    @property
    def connected(self) -> bool:
        """Check if the client is connected."""
        return bool(self._client.connected)

    def read_holding_registers(self, address: int, count: int, device_id: int) -> Any:
        """Read holding registers with version-agnostic device addressing."""
        kwargs = {self._device_kw: device_id}
        return self._client.read_holding_registers(
            address=address, count=count, **kwargs
        )

    def write_register(self, address: int, value: int, device_id: int) -> Any:
        """Write a single register with version-agnostic device addressing."""
        kwargs = {self._device_kw: device_id}
        return self._client.write_register(address=address, value=value, **kwargs)
