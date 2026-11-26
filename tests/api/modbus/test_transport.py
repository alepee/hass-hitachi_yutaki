"""Tests for the Modbus TCP transport (#519)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from pymodbus.exceptions import ConnectionException, ModbusException
import pytest

from custom_components.hitachi_yutaki.api.base import GatewayCommunicationError
from custom_components.hitachi_yutaki.api.modbus.compat import (
    get_pymodbus_device_param,
)
from custom_components.hitachi_yutaki.api.modbus.transport import ModbusTransport

MODULE = "custom_components.hitachi_yutaki.api.modbus.transport"


def _result(registers: list[int] | None = None, error: bool = False) -> MagicMock:
    result = MagicMock()
    result.isError.return_value = error
    result.registers = registers or []
    return result


@pytest.fixture
def mock_hass() -> MagicMock:
    """Run executor jobs inline."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda f, *a: f(*a))
    return hass


@pytest.fixture
def pymodbus_client() -> MagicMock:
    """Return a connected pymodbus client."""
    client = MagicMock()
    client.is_socket_open.return_value = True
    client.connect.return_value = True
    return client


@pytest.fixture
def transport(mock_hass, pymodbus_client) -> ModbusTransport:
    """Return a transport addressing device 7 through the mocked client."""
    transport = ModbusTransport(mock_hass, "127.0.0.1", 502, 7)
    transport._client = pymodbus_client
    return transport


@pytest.mark.asyncio
async def test_connect_builds_a_fresh_client(transport, pymodbus_client):
    """A connect closes the open socket and never reuses the old client."""
    fresh = MagicMock()
    fresh.connect.return_value = True
    fresh.is_socket_open.return_value = True

    with patch(f"{MODULE}.ModbusTcpClient", return_value=fresh) as factory:
        assert await transport.connect() is True

    pymodbus_client.close.assert_called_once()
    factory.assert_called_once_with(host="127.0.0.1", port=502)
    assert transport._client is fresh
    assert transport.connected is True


@pytest.mark.asyncio
async def test_connect_retries_with_backoff_then_gives_up(transport):
    """Three failed attempts, 1 s then 2 s apart, report a failed connection."""
    refused = MagicMock()
    refused.connect.return_value = False
    refused.is_socket_open.return_value = False

    with (
        patch(f"{MODULE}.ModbusTcpClient", return_value=refused),
        patch(f"{MODULE}.asyncio.sleep", new=AsyncMock()) as sleep,
    ):
        assert await transport.connect() is False

    assert refused.connect.call_count == 3
    assert [c.args[0] for c in sleep.await_args_list] == [1, 2]


@pytest.mark.asyncio
async def test_connect_survives_an_exception_on_one_attempt(transport):
    """An exception during an attempt is retried, not raised."""
    flaky = MagicMock()
    flaky.connect.side_effect = [OSError("refused"), True]
    flaky.is_socket_open.return_value = True

    with (
        patch(f"{MODULE}.ModbusTcpClient", return_value=flaky),
        patch(f"{MODULE}.asyncio.sleep", new=AsyncMock()),
    ):
        assert await transport.connect() is True


@pytest.mark.asyncio
async def test_reconnect_replaces_a_socket_that_fails_to_close(
    transport, pymodbus_client
):
    """A dead socket that still reports open and fails to close is replaced."""
    pymodbus_client.close.side_effect = OSError("broken pipe")
    fresh = MagicMock()
    fresh.connect.return_value = True
    fresh.is_socket_open.return_value = True

    with (
        patch(f"{MODULE}.ModbusTcpClient", return_value=fresh),
        patch(f"{MODULE}.asyncio.sleep", new=AsyncMock()) as sleep,
    ):
        assert await transport.reconnect() is True

    fresh.connect.assert_called_once()
    sleep.assert_not_awaited()
    assert transport._client is fresh


@pytest.mark.asyncio
async def test_reads_address_the_configured_device(transport, pymodbus_client):
    """Register operations carry the device id under the pymodbus parameter name."""
    pymodbus_client.read_holding_registers.return_value = _result([42])
    pymodbus_client.read_input_registers.return_value = _result([1, 2, 3])

    assert await transport.read_holding_registers(1050) == [42]
    assert await transport.read_input_registers(0, 3) == [1, 2, 3]

    param = get_pymodbus_device_param()
    assert pymodbus_client.read_holding_registers.call_args.kwargs == {
        "address": 1050,
        "count": 1,
        param: 7,
    }
    assert pymodbus_client.read_input_registers.call_args.kwargs == {
        "address": 0,
        "count": 3,
        param: 7,
    }


@pytest.mark.asyncio
async def test_error_responses_are_values_not_exceptions(
    transport, pymodbus_client, caplog
):
    """A Modbus exception response reads as None and writes as False."""
    pymodbus_client.read_holding_registers.return_value = _result(error=True)
    pymodbus_client.read_input_registers.return_value = _result(error=True)
    pymodbus_client.write_register.return_value = _result(error=True)

    assert await transport.read_holding_registers(1050) is None
    assert await transport.read_input_registers(0, 3) is None
    assert await transport.write_register(1001, 1) is False

    # The refusal detail stays visible without debug logging.
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 2
    assert all("Gateway refused" in r.getMessage() for r in warnings)


@pytest.mark.asyncio
async def test_write_reports_success(transport, pymodbus_client):
    """An accepted write returns True."""
    pymodbus_client.write_register.return_value = _result([1])

    assert await transport.write_register(1001, 1) is True
    assert pymodbus_client.write_register.call_args.kwargs["value"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        ModbusException("lost"),
        ConnectionException("no route"),
        ConnectionResetError("reset by peer"),
        TimeoutError(),
        OSError("socket error"),
    ],
)
@pytest.mark.parametrize(
    "operation",
    ["read_holding_registers", "read_input_registers", "write_register", "close"],
)
async def test_no_pymodbus_or_socket_exception_leaves_the_transport(
    transport, pymodbus_client, exc, operation
):
    """Every failure is translated, with the original kept as its cause."""
    getattr(pymodbus_client, operation).side_effect = exc
    args = {
        "read_holding_registers": (1050,),
        "read_input_registers": (0, 3),
        "write_register": (1001, 1),
        "close": (),
    }[operation]

    with pytest.raises(GatewayCommunicationError) as err:
        await getattr(transport, operation)(*args)

    assert err.value.__cause__ is exc
    assert type(exc).__name__ in str(err.value)


# --- Connection epoch (#476) ---


@pytest.mark.asyncio
async def test_each_connection_advances_the_epoch(transport):
    """connect() and reconnect() each open a new socket, hence a new epoch."""

    def fresh_client(**_kwargs) -> MagicMock:
        client = MagicMock()
        client.connect.return_value = True
        client.is_socket_open.return_value = True
        client.socket = object()
        return client

    with patch(f"{MODULE}.ModbusTcpClient", side_effect=fresh_client):
        assert await transport.connect() is True
        first = transport.connection_epoch
        assert await transport.reconnect() is True

    assert transport.connection_epoch == first + 1


@pytest.mark.asyncio
async def test_requests_on_the_same_socket_keep_the_epoch(transport, pymodbus_client):
    """Reads served by one socket all belong to one epoch."""
    pymodbus_client.read_holding_registers.return_value = _result([42])
    await transport.read_holding_registers(1050)
    epoch = transport.connection_epoch

    await transport.read_holding_registers(1051)
    await transport.write_register(1001, 1)

    assert transport.connection_epoch == epoch


@pytest.mark.asyncio
async def test_a_socket_pymodbus_reopens_on_its_own_advances_the_epoch(
    transport, pymodbus_client
):
    """Pymodbus reopens a closed socket before a request: that is a new connection.

    A gateway reboot closes the socket; the next request reconnects inside
    pymodbus without the transport being asked to, and reads the rebooted
    gateway.
    """
    pymodbus_client.socket = object()
    pymodbus_client.read_holding_registers.return_value = _result([42])
    await transport.read_holding_registers(1050)
    epoch = transport.connection_epoch

    def reopen_then_read(**_kwargs):
        pymodbus_client.socket = object()
        return _result([7])

    pymodbus_client.read_holding_registers.side_effect = reopen_then_read
    assert await transport.read_holding_registers(1050) == [7]

    assert transport.connection_epoch == epoch + 1


@pytest.mark.asyncio
async def test_a_closed_socket_alone_keeps_the_epoch(transport, pymodbus_client):
    """Closing is not a new connection; only the next socket is."""
    pymodbus_client.socket = object()
    await transport.read_holding_registers(1050)
    epoch = transport.connection_epoch

    pymodbus_client.socket = None
    await transport.close()

    assert transport.connection_epoch == epoch


@pytest.mark.asyncio
async def test_closed_transport_never_reopens_the_socket(transport, pymodbus_client):
    """After close, operations fail without reaching pymodbus.

    pymodbus reopens a closed socket when a request finds it closed, so a poll
    still in flight at unload would otherwise leave an orphan connection on a
    gateway that accepts few of them.
    """
    await transport.close()
    pymodbus_client.close.assert_called_once()

    with patch(f"{MODULE}.ModbusTcpClient") as factory:
        with pytest.raises(GatewayCommunicationError, match="closed"):
            await transport.read_holding_registers(1000)
        with pytest.raises(GatewayCommunicationError, match="closed"):
            await transport.write_register(1000, 1)
        assert await transport.reconnect() is False
        assert await transport.connect() is False

    factory.assert_not_called()
    pymodbus_client.read_holding_registers.assert_not_called()
    pymodbus_client.write_register.assert_not_called()
    pymodbus_client.connect.assert_not_called()


@pytest.mark.asyncio
async def test_operation_queued_behind_close_does_not_run(
    mock_hass, transport, pymodbus_client
):
    """A read waiting for the lock when close is called fails instead of reopening."""
    entered = asyncio.Event()
    release = asyncio.Event()
    calls: list[str] = []

    async def _executor(job, *args):
        calls.append(getattr(job, "__name__", "job"))
        if len(calls) == 1:
            entered.set()
            await release.wait()
        return job(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=_executor)
    pymodbus_client.read_holding_registers.return_value = _result([1])

    in_flight = asyncio.create_task(transport.read_holding_registers(1000))
    await entered.wait()
    closing = asyncio.create_task(transport.close())
    queued = asyncio.create_task(transport.read_holding_registers(1001))
    await asyncio.sleep(0)
    release.set()

    assert await in_flight == [1]  # The operation in flight is never cut off.
    await closing
    with pytest.raises(GatewayCommunicationError, match="closed"):
        await queued
    assert pymodbus_client.read_holding_registers.call_count == 1
