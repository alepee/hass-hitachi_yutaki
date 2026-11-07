"""Tests for the Modbus TCP transport (#519)."""

from __future__ import annotations

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
