"""Modbus TCP transport for the Hitachi gateways.

Only knows Modbus TCP: the connection, its reconnection, and the three
register operations the gateways need. Register maps, sentinels and every
gateway rule live in :class:`ModbusApiClient`, which receives a transport.

Register operations return plain values. A Modbus exception response from the
gateway is returned as ``None`` (reads) or ``False`` (writes); a communication
failure raises :class:`GatewayCommunicationError`, chained to the pymodbus or
socket exception, so the caller decides whether to reconnect and retry. No
pymodbus exception leaves this module.

Exception responses are logged with their detail (exception code): at WARNING
for input-register reads and writes, which callers do not expect to fail, and
at DEBUG for holding-register reads, where a refused read is routine (absent
sensor, fallback register).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import logging
from typing import Any

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.core import HomeAssistant

from ..base import GatewayCommunicationError
from .compat import get_pymodbus_device_param

_LOGGER = logging.getLogger(__name__)

DEFAULT_CONNECT_ATTEMPTS = 3


class ModbusTransport:
    """Modbus TCP connection to one gateway device."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        device_id: int,
        connect_attempts: int = DEFAULT_CONNECT_ATTEMPTS,
    ) -> None:
        """Initialize the transport; no I/O until connect()."""
        self._hass = hass
        self._host = host
        self._port = port
        self._device_id = device_id
        self._connect_attempts = connect_attempts
        self._device_param = get_pymodbus_device_param()
        self._client = ModbusTcpClient(host=host, port=port)

    @property
    def connected(self) -> bool:
        """Return True if the socket is open."""
        return self._client.is_socket_open()

    async def connect(self) -> bool:
        """Open a fresh connection, retrying with exponential backoff.

        Any open socket is closed first and a new pymodbus client is built,
        so a stale connection never survives a reconnect.
        """
        for attempt in range(self._connect_attempts):
            try:
                if self._client.is_socket_open():
                    # A dead socket may fail to close; the new client below
                    # replaces it either way.
                    with contextlib.suppress(Exception):
                        await self._hass.async_add_executor_job(self._client.close)

                self._client = ModbusTcpClient(host=self._host, port=self._port)
                success = await self._hass.async_add_executor_job(self._client.connect)

                if success and self._client.is_socket_open():
                    _LOGGER.debug(
                        "Successfully connected to Modbus gateway at %s:%s",
                        self._host,
                        self._port,
                    )
                    return True

                _LOGGER.warning(
                    "Failed to connect to Modbus gateway (attempt %d/%d)",
                    attempt + 1,
                    self._connect_attempts,
                )

            except Exception as exc:  # noqa: BLE001 - any failure means retry
                _LOGGER.warning(
                    "Connection attempt %d/%d failed: %s",
                    attempt + 1,
                    self._connect_attempts,
                    exc,
                )

            if attempt < self._connect_attempts - 1:
                await asyncio.sleep(2**attempt)  # 1s, 2s, 4s

        _LOGGER.error(
            "Failed to establish Modbus connection after %d attempts",
            self._connect_attempts,
        )
        return False

    async def reconnect(self) -> bool:
        """Drop the current socket, whatever its state, then connect again."""
        with contextlib.suppress(Exception):
            await self._hass.async_add_executor_job(self._client.close)
        return await self.connect()

    async def close(self) -> None:
        """Close the connection."""
        _LOGGER.debug("Closing connection to Modbus gateway")
        await self._run(self._client.close)

    async def _run(self, job: Callable[[], Any]) -> Any:
        """Run a blocking pymodbus call, translating its failures.

        pymodbus raises ``ModbusException`` (``ConnectionException`` included)
        and the socket raises ``OSError`` (``ConnectionError`` and
        ``TimeoutError`` included); both become GatewayCommunicationError.
        """
        try:
            return await self._hass.async_add_executor_job(job)
        except (ModbusException, OSError) as exc:
            raise GatewayCommunicationError(
                f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
            ) from exc

    async def read_holding_registers(
        self, address: int, count: int = 1
    ) -> list[int] | None:
        """Read holding registers (function code 03).

        Returns the registers, or None on a Modbus exception response.
        """
        result = await self._run(
            lambda: self._client.read_holding_registers(
                address=address, count=count, **{self._device_param: self._device_id}
            )
        )
        if result.isError():
            _LOGGER.debug("Error reading holding register %d: %s", address, result)
            return None
        return list(result.registers or [])

    async def read_input_registers(
        self, address: int, count: int = 1
    ) -> list[int] | None:
        """Read input registers (function code 04).

        Returns the registers, or None on a Modbus exception response.
        """
        result = await self._run(
            lambda: self._client.read_input_registers(
                address=address, count=count, **{self._device_param: self._device_id}
            )
        )
        if result.isError():
            _LOGGER.warning(
                "Gateway refused input registers %d-%d: %s",
                address,
                address + count - 1,
                result,
            )
            return None
        return list(result.registers or [])

    async def write_register(self, address: int, value: int) -> bool:
        """Write a single holding register (function code 06).

        Returns False on a Modbus exception response.
        """
        result = await self._run(
            lambda: self._client.write_register(
                address=address, value=value, **{self._device_param: self._device_id}
            )
        )
        if result.isError():
            _LOGGER.warning("Gateway refused write to register %d: %s", address, result)
            return False
        return True
