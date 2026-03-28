"""Test ModbusApiClient unique_id retrieval."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from pymodbus.exceptions import ModbusException
import pytest

from custom_components.hitachi_yutaki.api.base import ReadResult
from custom_components.hitachi_yutaki.api.modbus import ModbusApiClient
from custom_components.hitachi_yutaki.api.modbus.registers import RegisterDefinition
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
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


# --- Preflight / system_state deserialization tests ---


def _make_preflight_api_client(mock_hass, mock_client):
    """Create a ModbusApiClient with register map for preflight tests."""
    with patch.object(ModbusApiClient, "__init__", lambda x, *args, **kwargs: None):
        api = ModbusApiClient.__new__(ModbusApiClient)
        api._hass = mock_hass
        api._client = mock_client
        api._slave = 1
        api._data = {}
        api._register_map = AtwMbs02RegisterMap()
        api._gateway_not_ready_since = None
        api._gateway_not_ready_last_log = 0.0
        return api


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_deserializes_system_state_on_state_0(
    mock_ir, mock_hass, mock_client
):
    """Test system_state is deserialized to 'synchronized' when state is 0."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.read_holding_registers.return_value = _make_modbus_result(0)

    result = await api.read_values(["system_state"])

    assert result == ReadResult.SUCCESS
    assert api._data["system_state"] == "synchronized"


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_deserializes_system_state_on_state_2(
    mock_ir, mock_hass, mock_client
):
    """Test system_state is deserialized to 'initializing' when state is 2."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.read_holding_registers.return_value = _make_modbus_result(2)

    result = await api.read_values(["system_state"])

    assert result == ReadResult.GATEWAY_NOT_READY
    assert api._data["system_state"] == "initializing"


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_deserializes_system_state_on_state_1(
    mock_ir, mock_hass, mock_client
):
    """Test system_state is deserialized to 'desynchronized' when state is 1."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.read_holding_registers.return_value = _make_modbus_result(1)

    result = await api.read_values(["system_state"])

    assert result == ReadResult.GATEWAY_NOT_READY
    assert api._data["system_state"] == "desynchronized"


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_returns_success_on_normal_read(
    mock_ir, mock_hass, mock_client
):
    """Test read_values returns SUCCESS when gateway is synchronized."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.read_holding_registers.return_value = _make_modbus_result(0)

    result = await api.read_values(["system_state"])

    assert result == ReadResult.SUCCESS


@pytest.mark.asyncio
@patch("custom_components.hitachi_yutaki.api.modbus.ir")
async def test_read_values_throttles_gateway_not_ready_logs(
    _mock_ir, mock_hass, mock_client, caplog
):
    """Test that repeated gateway-not-ready warnings are throttled."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.read_holding_registers.return_value = _make_modbus_result(2)

    # First call should log
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        await api.read_values(["system_state"])
        first_warnings = [r for r in caplog.records if "not ready" in r.message]
        assert len(first_warnings) == 1

    # Second call immediately after should NOT log
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        await api.read_values(["system_state"])
        second_warnings = [r for r in caplog.records if "not ready" in r.message]
        assert len(second_warnings) == 0


@pytest.mark.asyncio
@patch("custom_components.hitachi_yutaki.api.modbus.ir")
async def test_read_values_logs_recovery_after_gateway_not_ready(
    _mock_ir, mock_hass, mock_client, caplog
):
    """Test that recovery is logged when gateway returns to normal."""
    api = _make_preflight_api_client(mock_hass, mock_client)

    # First: gateway not ready
    mock_client.read_holding_registers.return_value = _make_modbus_result(2)
    await api.read_values(["system_state"])

    # Then: gateway recovers
    mock_client.read_holding_registers.return_value = _make_modbus_result(0)
    with caplog.at_level(logging.INFO):
        caplog.clear()
        await api.read_values(["system_state"])
        recovery_logs = [r for r in caplog.records if "recovered" in r.message.lower()]
        assert len(recovery_logs) == 1


@pytest.mark.asyncio
@patch("custom_components.hitachi_yutaki.api.modbus.ir")
async def test_read_values_resets_throttle_state_on_recovery(
    _mock_ir, mock_hass, mock_client
):
    """Test that throttle state is reset after recovery."""
    api = _make_preflight_api_client(mock_hass, mock_client)

    # Not ready
    mock_client.read_holding_registers.return_value = _make_modbus_result(2)
    await api.read_values(["system_state"])
    assert api._gateway_not_ready_since is not None

    # Recovered
    mock_client.read_holding_registers.return_value = _make_modbus_result(0)
    await api.read_values(["system_state"])
    assert api._gateway_not_ready_since is None
    assert api._gateway_not_ready_last_log == 0.0


@pytest.mark.asyncio
@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@patch("custom_components.hitachi_yutaki.api.modbus.time")
async def test_read_values_logs_periodic_reminder_after_5_minutes(
    mock_time, _mock_ir, mock_hass, mock_client, caplog
):
    """Test that a periodic reminder is logged after 5 minutes of gateway-not-ready."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.read_holding_registers.return_value = _make_modbus_result(2)

    # First call at t=0
    mock_time.monotonic.return_value = 1000.0
    await api.read_values(["system_state"])

    # Second call at t=100s - should NOT log
    mock_time.monotonic.return_value = 1100.0
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        await api.read_values(["system_state"])
        warnings = [
            r
            for r in caplog.records
            if "not ready" in r.message.lower()
            or "still not ready" in r.message.lower()
        ]
        assert len(warnings) == 0

    # Third call at t=301s - SHOULD log periodic reminder
    mock_time.monotonic.return_value = 1301.0
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        await api.read_values(["system_state"])
        reminders = [
            r for r in caplog.records if "still not ready" in r.message.lower()
        ]
        assert len(reminders) == 1
        assert "5 minutes" in reminders[0].message
