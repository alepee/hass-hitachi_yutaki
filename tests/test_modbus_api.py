"""Test ModbusApiClient unique_id retrieval."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pymodbus.exceptions import ModbusException
import pytest

from custom_components.hitachi_yutaki.api.modbus import ModbusApiClient


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
    mock_client.read_input_registers.side_effect = ConnectionError("Network unreachable")

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
