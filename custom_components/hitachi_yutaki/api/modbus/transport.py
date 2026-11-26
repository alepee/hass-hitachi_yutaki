"""Modbus TCP transport for the Hitachi gateways.

Only knows Modbus TCP: the connection, its reconnection, and the three
register operations the gateways need. Register maps, sentinels and every
gateway rule live in :class:`ModbusApiClient`, which receives a transport.

One operation at a time: register operations, connection, reconnection and
close share one lock. The poll and the commands from Home Assistant share the
transport, so without it a reconnection started by a failed read could close
the socket under a write still waiting for its acknowledgement.

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
        # Held for the whole of each operation, so a reconnect or a close
        # never replaces the client under one in flight.
        self._lock = asyncio.Lock()
        # Socket the current epoch was counted on (identity only, never used).
        self._socket: object | None = None
        self._epoch = 0

    @property
    def connected(self) -> bool:
        """Return True if the socket is open."""
        return self._client.is_socket_open()

    @property
    def connection_epoch(self) -> int:
        """Return a number that changes whenever a new socket is opened.

        Counts every connection: the ones :meth:`connect` and :meth:`reconnect`
        open, and the ones pymodbus opens on its own when a request finds its
        socket closed. Readings taken under different epochs may come from a
        gateway that rebooted in between.
        """
        return self._epoch

    def _observe_socket(self) -> None:
        """Advance the epoch when the pymodbus client now holds a new socket."""
        sock = getattr(self._client, "socket", None)
        if sock is not None and sock is not self._socket:
            self._socket = sock
            self._epoch += 1

    async def connect(self) -> bool:
        """Open a fresh connection, retrying with exponential backoff.

        Any open socket is closed first and a new pymodbus client is built,
        so a stale connection never survives a reconnect. Waits for the
        operation in flight, if any.
        """
        async with self._lock:
            return await self._connect()

    async def _connect(self) -> bool:
        """Open a fresh connection; the caller holds the lock."""
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
                    self._observe_socket()
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
        """Drop the current socket, whatever its state, then connect again.

        Waits for the operation in flight, if any: it is never cut off.
        """
        async with self._lock:
            with contextlib.suppress(Exception):
                await self._hass.async_add_executor_job(self._client.close)
            return await self._connect()

    async def close(self) -> None:
        """Close the connection, once the operation in flight is over."""
        _LOGGER.debug("Closing connection to Modbus gateway")
        await self._run(self._close_client)

    def _close_client(self) -> None:
        """Close the client current when the lock is taken, not when queued."""
        self._client.close()

    async def _run(self, job: Callable[[], Any]) -> Any:
        """Run a blocking pymodbus call under the lock, translating its failures.

        pymodbus raises ``ModbusException`` (``ConnectionException`` included)
        and the socket raises ``OSError`` (``ConnectionError`` and
        ``TimeoutError`` included); both become GatewayCommunicationError.
        pymodbus reopens a closed socket before sending a request, so the
        epoch is checked after every call, whatever its outcome.
        """
        try:
            async with self._lock:
                try:
                    return await self._hass.async_add_executor_job(job)
                finally:
                    self._observe_socket()
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
