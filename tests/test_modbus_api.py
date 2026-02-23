"""Test ModbusApiClient unique_id retrieval."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pymodbus.exceptions import ModbusException
import pytest

from custom_components.hitachi_yutaki.api.modbus import ModbusApiClient
from custom_components.hitachi_yutaki.api.modbus.registers import RegisterDefinition
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    convert_signed_16bit,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda f: f())
    return hass


@pytest.fixture
def mock_client():
    """Create a mock Modbus client."""
    client = MagicMock()
    client.is_socket_open.return_value = True
    return client


@pytest.fixture
def api_client(mock_hass, mock_client):
    """Create a ModbusApiClient instance with mocked dependencies."""
    with patch.object(ModbusApiClient, "__init__", lambda x, *args, **kwargs: None):
        api = ModbusApiClient.__new__(ModbusApiClient)
        api._hass = mock_hass
        api._client = mock_client
        api._slave = 1
        return api


@pytest.mark.asyncio
async def test_async_get_unique_id_success(api_client, mock_client):
    """Test successful unique_id retrieval from input registers."""
    mock_result = MagicMock()
    mock_result.isError.return_value = False
    mock_result.registers = [3846, 103, 56]
    mock_client.read_input_registers.return_value = mock_result

    result = await api_client.async_get_unique_id()

    assert result == "3846-103-56"
    mock_client.read_input_registers.assert_called_once()


@pytest.mark.asyncio
async def test_async_get_unique_id_different_values(api_client, mock_client):
    """Test unique_id with different register values."""
    mock_result = MagicMock()
    mock_result.isError.return_value = False
    mock_result.registers = [1234, 5678, 9012]
    mock_client.read_input_registers.return_value = mock_result

    result = await api_client.async_get_unique_id()

    assert result == "1234-5678-9012"


@pytest.mark.asyncio
async def test_async_get_unique_id_modbus_error(api_client, mock_client):
    """Test unique_id retrieval when Modbus returns error."""
    mock_result = MagicMock()
    mock_result.isError.return_value = True
    mock_client.read_input_registers.return_value = mock_result

    result = await api_client.async_get_unique_id()

    assert result is None


@pytest.mark.asyncio
async def test_async_get_unique_id_modbus_exception(api_client, mock_client):
    """Test unique_id retrieval when ModbusException is raised."""
    mock_client.read_input_registers.side_effect = ModbusException("Connection lost")

    result = await api_client.async_get_unique_id()

    assert result is None


@pytest.mark.asyncio
async def test_async_get_unique_id_connection_error(api_client, mock_client):
    """Test unique_id retrieval when ConnectionError occurs."""
    mock_client.read_input_registers.side_effect = ConnectionError(
        "Network unreachable"
    )

    result = await api_client.async_get_unique_id()

    assert result is None


@pytest.mark.asyncio
async def test_async_get_unique_id_os_error(api_client, mock_client):
    """Test unique_id retrieval when OSError occurs."""
    mock_client.read_input_registers.side_effect = OSError("Socket error")

    result = await api_client.async_get_unique_id()

    assert result is None


@pytest.mark.asyncio
async def test_async_get_unique_id_insufficient_registers(api_client, mock_client):
    """Test unique_id retrieval when fewer than 3 registers returned."""
    mock_result = MagicMock()
    mock_result.isError.return_value = False
    mock_result.registers = [3846, 103]  # Only 2 registers
    mock_client.read_input_registers.return_value = mock_result

    result = await api_client.async_get_unique_id()

    assert result is None


@pytest.mark.asyncio
async def test_async_get_unique_id_zero_values(api_client, mock_client):
    """Test unique_id with zero register values."""
    mock_result = MagicMock()
    mock_result.isError.return_value = False
    mock_result.registers = [0, 0, 0]
    mock_client.read_input_registers.return_value = mock_result

    result = await api_client.async_get_unique_id()

    # Zero values are still valid
    assert result == "0-0-0"


@pytest.mark.asyncio
async def test_async_get_unique_id_max_values(api_client, mock_client):
    """Test unique_id with maximum register values (16-bit)."""
    mock_result = MagicMock()
    mock_result.isError.return_value = False
    mock_result.registers = [65535, 65535, 65535]
    mock_client.read_input_registers.return_value = mock_result

    result = await api_client.async_get_unique_id()

    assert result == "65535-65535-65535"


@pytest.mark.asyncio
async def test_async_get_unique_id_more_than_three_registers(api_client, mock_client):
    """Test unique_id when more than 3 registers returned (uses first 3)."""
    mock_result = MagicMock()
    mock_result.isError.return_value = False
    mock_result.registers = [3846, 103, 56, 999, 888]  # Extra registers
    mock_client.read_input_registers.return_value = mock_result

    result = await api_client.async_get_unique_id()

    # Should only use the first 3 registers
    assert result == "3846-103-56"


# --- Register fallback tests ---


def _make_modbus_result(value: int):
    """Create a mock Modbus result with a single register value."""
    result = MagicMock()
    result.isError.return_value = False
    result.registers = [value]
    return result


def _make_modbus_error():
    """Create a mock Modbus error result."""
    result = MagicMock()
    result.isError.return_value = True
    return result


@pytest.mark.asyncio
async def test_read_register_returns_deserialized_value(api_client, mock_client):
    """Test _read_register returns deserialized value on success."""
    mock_client.read_holding_registers.return_value = _make_modbus_result(350)
    definition = RegisterDefinition(1200, deserializer=lambda v: v / 10.0)

    value = await api_client._read_register(definition, "slave")

    assert value == 35.0


@pytest.mark.asyncio
async def test_read_register_returns_raw_value_without_deserializer(
    api_client, mock_client
):
    """Test _read_register returns raw value when no deserializer is set."""
    mock_client.read_holding_registers.return_value = _make_modbus_result(42)
    definition = RegisterDefinition(1000)

    value = await api_client._read_register(definition, "slave")

    assert value == 42


@pytest.mark.asyncio
async def test_read_register_returns_none_on_error(api_client, mock_client):
    """Test _read_register returns None on Modbus read error."""
    mock_client.read_holding_registers.return_value = _make_modbus_error()
    definition = RegisterDefinition(1200)

    value = await api_client._read_register(definition, "slave")

    assert value is None


@pytest.mark.asyncio
async def test_fallback_used_when_primary_returns_none(api_client, mock_client):
    """Test that fallback register is read when primary deserializes to None."""
    # Primary returns 0xFFFF (sensor error) → convert_signed_16bit returns None
    # Fallback returns valid value
    primary_result = _make_modbus_result(0xFFFF)
    fallback_result = _make_modbus_result(350)  # 35.0°C as signed 16-bit

    mock_client.read_holding_registers.side_effect = [primary_result, fallback_result]

    definition = RegisterDefinition(
        1200,
        deserializer=convert_signed_16bit,
        fallback=RegisterDefinition(1093, deserializer=convert_signed_16bit),
    )

    # Simulate the read_values fallback logic
    value = await api_client._read_register(definition, "slave")
    if value is None and definition.fallback:
        value = await api_client._read_register(definition.fallback, "slave")

    assert value == 350
    assert mock_client.read_holding_registers.call_count == 2


@pytest.mark.asyncio
async def test_fallback_not_used_when_primary_succeeds(api_client, mock_client):
    """Test that fallback is NOT read when primary returns a valid value."""
    mock_client.read_holding_registers.return_value = _make_modbus_result(350)

    definition = RegisterDefinition(
        1200,
        deserializer=lambda v: v,
        fallback=RegisterDefinition(1093, deserializer=lambda v: v),
    )

    value = await api_client._read_register(definition, "slave")
    if value is None and definition.fallback:
        value = await api_client._read_register(definition.fallback, "slave")

    assert value == 350
    # Only one read — fallback was never called
    assert mock_client.read_holding_registers.call_count == 1


@pytest.mark.asyncio
async def test_fallback_used_when_primary_read_errors(api_client, mock_client):
    """Test that fallback is read when primary has a Modbus read error."""
    primary_result = _make_modbus_error()
    fallback_result = _make_modbus_result(280)

    mock_client.read_holding_registers.side_effect = [primary_result, fallback_result]

    definition = RegisterDefinition(
        1200,
        fallback=RegisterDefinition(1093),
    )

    value = await api_client._read_register(definition, "slave")
    if value is None and definition.fallback:
        value = await api_client._read_register(definition.fallback, "slave")

    assert value == 280
    assert mock_client.read_holding_registers.call_count == 2


@pytest.mark.asyncio
async def test_fallback_also_fails_returns_none(api_client, mock_client):
    """Test that None is returned when both primary and fallback fail."""
    mock_client.read_holding_registers.return_value = _make_modbus_error()

    definition = RegisterDefinition(
        1200,
        fallback=RegisterDefinition(1093),
    )

    value = await api_client._read_register(definition, "slave")
    if value is None and definition.fallback:
        value = await api_client._read_register(definition.fallback, "slave")

    assert value is None
    assert mock_client.read_holding_registers.call_count == 2
