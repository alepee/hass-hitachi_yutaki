"""Test ModbusApiClient unique_id retrieval."""

from __future__ import annotations

import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

from pymodbus.exceptions import ModbusException
import pytest

from custom_components.hitachi_yutaki.api.base import ReadResult
from custom_components.hitachi_yutaki.api.modbus import (
    MAX_RESTORE_ATTEMPTS,
    ModbusApiClient,
)
from custom_components.hitachi_yutaki.api.modbus.registers import RegisterDefinition
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
    convert_signed_16bit,
)
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02_pre2016 import (
    AtwMbs02Pre2016RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.hc_a_mb import (
    HcAMbRegisterMap,
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
        api._pending_writes = {}
        api._kept = {}
        api._kept_changed = False
        api._restore_attempts = {}
        api._restore_failed = set()
        api._writing_back = None
        api._lost = {}
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
        api._pending_writes = {}
        api._kept = {}
        api._kept_changed = False
        api._restore_attempts = {}
        api._restore_failed = set()
        api._writing_back = None
        api._lost = {}
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
async def test_read_values_resets_throttle_state_on_recovery(
    _mock_ir, mock_hass, mock_client, caplog
):
    """Test that throttle state is reset and a recovery line is logged (#356)."""
    api = _make_preflight_api_client(mock_hass, mock_client)

    # Not ready
    mock_client.read_holding_registers.return_value = _make_modbus_result(2)
    await api.read_values(["system_state"])
    assert api._gateway_not_ready_since is not None

    # Recovered
    mock_client.read_holding_registers.return_value = _make_modbus_result(0)
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        await api.read_values(["system_state"])
    assert api._gateway_not_ready_since is None
    assert api._gateway_not_ready_last_log == 0.0
    recovery_logs = [r for r in caplog.records if "recovered" in r.message.lower()]
    assert len(recovery_logs) == 1


# --- Stale-value clearing on sensor-error / read-error (issue #320) ---


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_clears_stale_value_on_sensor_error_without_fallback(
    _mock_ir, mock_hass, mock_client
):
    """A 0xFFFF sensor-error with no fallback must clear the stale value (#320)."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    api._data["outdoor_temp"] = 5  # stale good value

    # [preflight system_state, outdoor_temp = 0xFFFF sensor error]
    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_result(0xFFFF),
    ]

    result = await api.read_values(["outdoor_temp"])

    assert result == ReadResult.SUCCESS
    assert "outdoor_temp" not in api._data


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_clears_stale_value_on_read_error_without_fallback(
    _mock_ir, mock_hass, mock_client
):
    """A per-register read error with no fallback must clear the stale value (#320)."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    api._data["outdoor_temp"] = 5  # stale good value

    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_error(),
    ]

    result = await api.read_values(["outdoor_temp"])

    assert result == ReadResult.SUCCESS
    assert "outdoor_temp" not in api._data


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_keeps_value_on_successful_read(
    _mock_ir, mock_hass, mock_client
):
    """A fresh successful read overwrites the stored value (regression guard)."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    api._data["outdoor_temp"] = 5  # stale value to be overwritten

    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_result(200),  # convert_signed_16bit(200) == 200
    ]

    result = await api.read_values(["outdoor_temp"])

    assert result == ReadResult.SUCCESS
    assert api._data["outdoor_temp"] == 200


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_fallback_still_recovers_on_sensor_error(
    _mock_ir, mock_hass, mock_client
):
    """Fallback register must still recover when primary is a 0xFFFF sensor-error."""
    api = _make_preflight_api_client(mock_hass, mock_client)

    # [preflight, primary 1200 = 0xFFFF, fallback 1093 = 350]
    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_result(0xFFFF),
        _make_modbus_result(350),
    ]

    result = await api.read_values(["water_outlet_temp"])

    assert result == ReadResult.SUCCESS
    assert api._data["water_outlet_temp"] == 350


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_clears_when_both_primary_and_fallback_error(
    _mock_ir, mock_hass, mock_client
):
    """When both primary and fallback error, the stale value must be cleared (#320)."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    api._data["water_outlet_temp"] = 42  # stale good value

    # [preflight, primary 1200 = 0xFFFF, fallback 1093 = 0xFFFF]
    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_result(0xFFFF),
        _make_modbus_result(0xFFFF),
    ]

    result = await api.read_values(["water_outlet_temp"])

    assert result == ReadResult.SUCCESS
    assert "water_outlet_temp" not in api._data


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


def test_get_operation_state_reads_data():
    """get_operation_state returns the deserialized operation_state from _data."""
    with patch.object(ModbusApiClient, "__init__", lambda x, *args, **kwargs: None):
        api = ModbusApiClient.__new__(ModbusApiClient)
        api._data = {"operation_state": "operation_state_heat_thermo_on"}
        assert api.get_operation_state() == "operation_state_heat_thermo_on"


def test_get_operation_state_absent_returns_none():
    """get_operation_state returns None when operation_state is absent."""
    with patch.object(ModbusApiClient, "__init__", lambda x, *args, **kwargs: None):
        api = ModbusApiClient.__new__(ModbusApiClient)
        api._data = {}
        assert api.get_operation_state() is None


@pytest.fixture
def pre2016_api_client(mock_hass, mock_client):
    """Create a ModbusApiClient wired with the pre-2016 register map for write tests."""
    with patch.object(ModbusApiClient, "__init__", lambda x, *args, **kwargs: None):
        api = ModbusApiClient.__new__(ModbusApiClient)
        api._hass = mock_hass
        api._client = mock_client
        api._slave = 1
        api._register_map = AtwMbs02Pre2016RegisterMap()
        api._data = {}
        api._pending_writes = {}
        api._kept = {}
        api._kept_changed = False
        api._restore_attempts = {}
        api._restore_failed = set()
        api._writing_back = None
        api._lost = {}
        write_result = MagicMock()
        write_result.isError.return_value = False
        mock_client.write_register.return_value = write_result
        return api


class TestGlobalEcoAccessors:
    """Behavior of the global (pre-2016) eco accessors.

    The pre-2016 Space mode register is NON-inverted (0=Comfort, 1=ECO),
    unlike the 2016+ per-circuit eco registers which are inverted
    (0=eco, 1=comfort). These tests lock that convention in.
    """

    def test_get_eco_mode_non_inverted(self, pre2016_api_client):
        """Raw 1 means ECO on, raw 0 means Comfort (off), absent means None."""
        pre2016_api_client._data = {"eco_mode": 1}
        assert pre2016_api_client.get_eco_mode() is True
        pre2016_api_client._data = {"eco_mode": 0}
        assert pre2016_api_client.get_eco_mode() is False
        pre2016_api_client._data = {}
        assert pre2016_api_client.get_eco_mode() is None

    @pytest.mark.asyncio
    async def test_set_eco_mode_writes_raw_1_at_1027(
        self, pre2016_api_client, mock_client
    ):
        """Enabling ECO writes raw 1 (non-inverted) to address 1027."""
        assert await pre2016_api_client.set_eco_mode(True) is True
        kwargs = mock_client.write_register.call_args.kwargs
        assert kwargs["address"] == 1027
        assert kwargs["value"] == 1

    @pytest.mark.asyncio
    async def test_set_eco_mode_writes_raw_0_when_disabled(
        self, pre2016_api_client, mock_client
    ):
        """Disabling ECO writes raw 0 (Comfort) to address 1027."""
        assert await pre2016_api_client.set_eco_mode(False) is True
        kwargs = mock_client.write_register.call_args.kwargs
        assert kwargs["address"] == 1027
        assert kwargs["value"] == 0

    def test_get_eco_offset_reads_data(self, pre2016_api_client):
        """get_eco_offset returns the raw buffered value, None when absent."""
        pre2016_api_client._data = {"eco_offset": 4}
        assert pre2016_api_client.get_eco_offset() == 4
        pre2016_api_client._data = {}
        assert pre2016_api_client.get_eco_offset() is None

    @pytest.mark.asyncio
    async def test_set_eco_offset_writes_control_address_1030(
        self, pre2016_api_client, mock_client
    ):
        """A valid offset is written to CONTROL 1030, not STATUS 1090."""
        assert await pre2016_api_client.set_eco_offset(5) is True
        kwargs = mock_client.write_register.call_args.kwargs
        assert kwargs["address"] == 1030
        assert kwargs["value"] == 5

    @pytest.mark.asyncio
    @pytest.mark.parametrize("offset", [0, 11])
    async def test_set_eco_offset_rejects_out_of_range_without_write(
        self, pre2016_api_client, mock_client, offset
    ):
        """Out-of-range offsets are rejected before any Modbus write."""
        assert await pre2016_api_client.set_eco_offset(offset) is False
        mock_client.write_register.assert_not_called()


# --- Garbage system_config read (issue #404) ---


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_filters_garbage_system_config(
    _mock_ir, mock_hass, mock_client
):
    """A 0xFFFF system_config is filtered, not decoded as every capability (#404)."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    api._data["system_config"] = 0x0021  # stale good value

    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_result(0xFFFF),
    ]

    result = await api.read_values(["system_config"])

    assert result == ReadResult.SUCCESS
    assert "system_config" not in api._data
    assert api.has_dhw is False
    assert api.has_pool is False


@pytest.mark.parametrize(
    "register_map",
    [AtwMbs02RegisterMap(), AtwMbs02Pre2016RegisterMap(), HcAMbRegisterMap()],
    ids=["atw_mbs_02", "atw_mbs_02_pre2016", "hc_a_mb"],
)
def test_system_config_declares_garbage_sentinel(register_map):
    """Every register map filters a 0xFFFF system_config (#404)."""
    sentinels = register_map.all_registers["system_config"].sentinel_values
    assert sentinels is not None
    assert 0xFFFF in sentinels


@pytest.mark.parametrize(
    "register_map",
    [AtwMbs02RegisterMap(), AtwMbs02Pre2016RegisterMap(), HcAMbRegisterMap()],
    ids=["atw_mbs_02", "atw_mbs_02_pre2016", "hc_a_mb"],
)
@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_system_state_ffff_is_not_ready(
    mock_ir, mock_hass, mock_client, register_map
):
    """A 0xFFFF system_state (no heat pump data) is not ready, not healthy (#404)."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    api._register_map = register_map
    mock_client.read_holding_registers.return_value = _make_modbus_result(0xFFFF)

    result = await api.read_values(["system_config"])

    assert result == ReadResult.GATEWAY_NOT_READY
    assert "system_config" not in api._data
    assert mock_client.read_holding_registers.call_count == 1
    mock_ir.async_create_issue.assert_called_once()
    assert mock_ir.async_create_issue.call_args.args[2] == "no_data_warning"


# --- Pending writes: a command must not show up, revert, then show up again ---


@pytest.mark.asyncio
async def test_write_value_publishes_expected_value_at_once(mock_hass, mock_client):
    """A successful write is visible in ``_data`` before any poll, deserialized."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    api._data["circuit1_target_temp"] = 21.0
    mock_client.write_register.return_value = _make_modbus_result(0)

    assert await api.write_value("circuit1_target_temp", 225) is True

    assert api._data["circuit1_target_temp"] == 22.5
    assert api._pending_writes["circuit1_target_temp"][0] == 22.5
    assert mock_client.write_register.call_args.kwargs["address"] == 1011


@pytest.mark.asyncio
async def test_failed_write_shadows_nothing(mock_hass, mock_client):
    """A refused write leaves both the data and the pending map untouched (#322)."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    api._data["unit_power"] = 0
    mock_client.write_register.return_value = _make_modbus_error()
    api._ensure_connection = AsyncMock(return_value=False)

    assert await api.write_value("unit_power", 1) is False

    assert api._data["unit_power"] == 0
    assert api._pending_writes == {}


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_ignores_stale_status_after_write(
    _mock_ir, mock_hass, mock_client
):
    """Polls still reporting the pre-write value do not revert the entity."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.write_register.return_value = _make_modbus_result(0)
    await api.write_value("unit_power", 1)

    # [preflight system_state, unit_power still 0 on the gateway]
    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_result(0),
    ]
    assert await api.read_values(["unit_power"]) == ReadResult.SUCCESS
    assert api._data["unit_power"] == 1

    # A read error in the window keeps the expected value too (not #320's clear).
    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_error(),
    ]
    assert await api.read_values(["unit_power"]) == ReadResult.SUCCESS
    assert api._data["unit_power"] == 1
    assert "unit_power" in api._pending_writes


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_confirms_write_and_lifts_shadow(
    _mock_ir, mock_hass, mock_client
):
    """A STATUS read equal to the written value ends the shadow."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.write_register.return_value = _make_modbus_result(0)
    await api.write_value("unit_power", 1)

    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_result(1),
    ]
    await api.read_values(["unit_power"])
    assert api._pending_writes == {}

    # From then on the gateway is the truth again (e.g. the unit turned off).
    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_result(0),
    ]
    await api.read_values(["unit_power"])
    assert api._data["unit_power"] == 0


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_accepts_gateway_value_after_ttl(
    _mock_ir, mock_hass, mock_client
):
    """Past the deadline an unconfirmed write yields to the gateway value."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.write_register.return_value = _make_modbus_result(0)
    await api.write_value("unit_power", 1)
    api._pending_writes["unit_power"] = (1, time.monotonic() - 1)

    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_result(0),
    ]
    await api.read_values(["unit_power"])

    assert api._data["unit_power"] == 0
    assert api._pending_writes == {}


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_successive_writes_last_value_wins_and_rearms_deadline(
    _mock_ir, mock_hass, mock_client
):
    """On -> off on one key: the last expected value, with a later deadline."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.write_register.return_value = _make_modbus_result(0)
    await api.write_value("unit_power", 1)
    expected, deadline = api._pending_writes["unit_power"]
    earlier = deadline - 5
    api._pending_writes["unit_power"] = (expected, earlier)

    await api.write_value("unit_power", 0)

    expected, deadline = api._pending_writes["unit_power"]
    assert (expected, api._data["unit_power"]) == (0, 0)
    assert deadline > earlier

    # The first write's value is stale now, not a confirmation.
    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_result(1),
    ]
    await api.read_values(["unit_power"])
    assert api._data["unit_power"] == 0
    assert "unit_power" in api._pending_writes


# --- Outdoor readings zeroed by a lost outdoor unit (#457) ---


def _outdoor_link_api_client(mock_hass, mock_client, data):
    api = _make_preflight_api_client(mock_hass, mock_client)
    api._data = dict(data)
    return api


@pytest.mark.parametrize(
    "register_map",
    [AtwMbs02RegisterMap(), AtwMbs02Pre2016RegisterMap(), HcAMbRegisterMap()],
    ids=["atw_mbs_02", "atw_mbs_02_pre2016", "hc_a_mb"],
)
def test_outdoor_unit_keys_cover_outdoor_side_only(register_map):
    """Outdoor ambient and outdoor-side compressor data, not indoor Tg/Ti/EVI."""
    keys = set(register_map.outdoor_unit_keys)
    assert {"outdoor_temp", "compressor_td_discharge_temp"} <= keys
    assert keys.isdisjoint(
        {
            "compressor_tg_gas_temp",
            "compressor_ti_liquid_temp",
            "compressor_evi_indoor_expansion_valve_opening",
        }
    )
    assert keys <= set(register_map.all_registers)


def test_outdoor_link_alarm_drops_zeroed_outdoor_readings(mock_hass, mock_client):
    """On alarm 03 the zeros relayed from the outdoor unit become unavailable."""
    api = _outdoor_link_api_client(
        mock_hass,
        mock_client,
        {
            "alarm_code": "alarm_code_3",
            "outdoor_temp": 0,
            "compressor_frequency": 0,
            "compressor_tg_gas_temp": 0,
            "dhw_current_temp": 36,
        },
    )
    assert api.outdoor_link_lost is True

    api._gate_outdoor_link_loss()

    assert "outdoor_temp" not in api._data
    assert "compressor_frequency" not in api._data
    # Indoor-side readings are left alone, even at 0.
    assert api._data["compressor_tg_gas_temp"] == 0
    assert api._data["dhw_current_temp"] == 36


def test_outdoor_link_alarm_keeps_auxiliary_outdoor_sensor(mock_hass, mock_client):
    """A non-zero outdoor temperature (auxiliary sensor on the indoor unit) stays."""
    api = _outdoor_link_api_client(
        mock_hass, mock_client, {"alarm_code": "alarm_code_3", "outdoor_temp": 7}
    )

    api._gate_outdoor_link_loss()

    assert api._data["outdoor_temp"] == 7


@pytest.mark.parametrize("alarm_code", ["alarm_code_0", "alarm_code_2"])
def test_zero_outdoor_reading_kept_without_outdoor_link_alarm(
    mock_hass, mock_client, alarm_code
):
    """Outside alarm 03, 0 °C is a real outdoor temperature."""
    api = _outdoor_link_api_client(
        mock_hass, mock_client, {"alarm_code": alarm_code, "outdoor_temp": 0}
    )
    assert api.outdoor_link_lost is False

    api._gate_outdoor_link_loss()

    assert api._data["outdoor_temp"] == 0


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_gates_outdoor_link_loss(_mock_ir, mock_hass, mock_client):
    """read_values applies the gate after reading the alarm code."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),  # preflight system_state
        _make_modbus_result(0),  # outdoor_temp
        _make_modbus_result(3),  # alarm_code
    ]

    result = await api.read_values(["outdoor_temp", "alarm_code"])

    assert result == ReadResult.SUCCESS
    assert api._data["alarm_code"] == "alarm_code_3"
    assert "outdoor_temp" not in api._data


# --- Room settings a reboot takes from the hardware (#511) ---

ROOM_KEYS = ["circuit1_thermostat", "circuit1_target_temp", "circuit1_current_temp"]


async def _poll(
    api, mock_client, flag: int, target: int, room: int = 215, state: int = 0
):
    """Run one poll of circuit 1's flag, room target and room value (raw tenths)."""
    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(state),
        _make_modbus_result(flag),
        _make_modbus_result(target),
        _make_modbus_result(room),
    ]
    result = await api.read_values(ROOM_KEYS)
    await api.restore_lost_values()
    return result


def _room_api(mock_hass, mock_client):
    """Client on the 2016 map with writes accepted (circuit 1 is never gated)."""
    api = _make_preflight_api_client(mock_hass, mock_client)
    mock_client.write_register.return_value = _make_modbus_result(0)
    return api


def _writes(mock_client) -> list[tuple[int, int]]:
    return [
        (c.kwargs["address"], c.kwargs["value"])
        for c in mock_client.write_register.call_args_list
    ]


def _expire_pending(api) -> None:
    """Move every pending write past its deadline."""
    for key, (expected, _) in api._pending_writes.items():
        api._pending_writes[key] = (expected, time.monotonic() - 1)


def test_room_settings_are_kept_on_the_2016_map():
    """Flag and room target of both circuits are declared as kept values."""
    regs = AtwMbs02RegisterMap().all_registers
    for cid in (1, 2):
        assert regs[f"circuit{cid}_thermostat"].keep is not None
        target = regs[f"circuit{cid}_target_temp"].keep
        assert target.valid_range == (5.0, 35.0)
        assert target.while_on == f"circuit{cid}_thermostat"
        assert regs[f"circuit{cid}_current_temp"].keep is None


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_controller_reboot_restores_target_and_seeds_room(
    _mock_ir, mock_hass, mock_client
):
    """Target and room zeroed, flag still on: target back, room = target."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)
    assert _writes(mock_client) == []

    await _poll(api, mock_client, flag=1, target=0, room=0)

    # Without the seed the unit would heat on 0 °C against 22 °C.
    assert _writes(mock_client) == [(1011, 220), (1012, 220)]
    assert api._data["circuit1_target_temp"] == 22.0


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_read_values_only_queues_lost_values(_mock_ir, mock_hass, mock_client):
    """Reading never writes; the restore is a separate command."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)
    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_result(1),
        _make_modbus_result(0),
        _make_modbus_result(0),
    ]

    await api.read_values(ROOM_KEYS)
    assert _writes(mock_client) == []

    await api.restore_lost_values()
    assert _writes(mock_client) == [(1011, 220), (1012, 220)]

    # The queue is consumed: a second call writes nothing more.
    await api.restore_lost_values()
    assert len(_writes(mock_client)) == 2


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_target_written_back_keeps_a_room_value_that_survived(
    _mock_ir, mock_hass, mock_client
):
    """A room value still read is the last one fed: it is not overwritten."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)

    await _poll(api, mock_client, flag=1, target=0, room=215)

    assert _writes(mock_client) == [(1011, 220)]


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_room_target_left_alone_with_the_flag_off(
    _mock_ir, mock_hass, mock_client
):
    """With the flag off the unit ignores the room registers: no write."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=0, target=220)
    await _poll(api, mock_client, flag=0, target=0)

    assert _writes(mock_client) == []
    assert api.failed_restore_circuits() == []


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_gateway_reboot_raises_the_flag_again(_mock_ir, mock_hass, mock_client):
    """Flag cleared, target and room kept: only the flag is written back."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)

    await _poll(api, mock_client, flag=0, target=220, room=215)

    assert _writes(mock_client) == [(1010, 1)]


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_flag_raised_on_a_zeroed_room_seeds_it_first(
    _mock_ir, mock_hass, mock_client
):
    """No room value to regulate on: it is seeded before the flag goes up."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)

    await _poll(api, mock_client, flag=0, target=220, room=0)

    assert _writes(mock_client) == [(1012, 220), (1010, 1)]


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_full_power_cut_restores_target_then_flag(
    _mock_ir, mock_hass, mock_client
):
    """Gateway, controller and HA restart together: references come from the store."""
    api = _room_api(mock_hass, mock_client)
    api.restore_kept_values({"circuit1_thermostat": 1, "circuit1_target_temp": 22.0})

    # While the gateway resyncs nothing is read, nothing written.
    assert (
        await _poll(api, mock_client, flag=0, target=0, room=0, state=2)
        == ReadResult.GATEWAY_NOT_READY
    )
    assert _writes(mock_client) == []

    # The target goes back first; the flag waits for the unit to confirm it.
    await _poll(api, mock_client, flag=0, target=0, room=0)
    assert _writes(mock_client) == [(1011, 220)]

    await _poll(api, mock_client, flag=0, target=220, room=0)
    assert _writes(mock_client) == [(1011, 220), (1012, 220), (1010, 1)]


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_flag_stays_down_while_the_target_is_dropped(
    _mock_ir, mock_hass, mock_client
):
    """A target written back but refused never lets the flag up."""
    api = _room_api(mock_hass, mock_client)
    api.restore_kept_values({"circuit1_thermostat": 1, "circuit1_target_temp": 22.0})
    for _ in range(6):
        await _poll(api, mock_client, flag=0, target=0, room=0)
        _expire_pending(api)

    assert (1010, 1) not in _writes(mock_client)
    assert api.failed_restore_circuits() == [1]


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_flag_turned_off_from_home_assistant_stays_off(
    _mock_ir, mock_hass, mock_client
):
    """A flag lowered by a write is the new reference, not a lost value."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)
    assert await api.set_external_room_sensor(1, False)
    mock_client.write_register.reset_mock()

    await _poll(api, mock_client, flag=0, target=220)

    assert _writes(mock_client) == []
    assert api.kept_values()["circuit1_thermostat"] == 0


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_switch_turned_off_during_a_write_back_wins(
    _mock_ir, mock_hass, mock_client
):
    """Home Assistant lowers the flag while the room is seeded: no raise after it."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)

    def user_turns_off_during_seed(**kwargs):
        if kwargs["address"] == 1012:
            api._kept["circuit1_thermostat"] = 0
        return _make_modbus_result(0)

    mock_client.write_register.side_effect = user_turns_off_during_seed
    await _poll(api, mock_client, flag=0, target=220, room=0)

    assert (1010, 1) not in _writes(mock_client)


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_target_changed_on_the_controller_becomes_the_reference(
    _mock_ir, mock_hass, mock_client
):
    """A valid reading follows the controller, so it is what comes back."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)
    await _poll(api, mock_client, flag=1, target=195)

    await _poll(api, mock_client, flag=1, target=0)

    assert _writes(mock_client) == [(1011, 195)]


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_flag_without_a_known_target_is_reported(
    _mock_ir, mock_hass, mock_client
):
    """No target to write back: the flag stays down and the user is told."""
    api = _room_api(mock_hass, mock_client)
    api.restore_kept_values({"circuit1_thermostat": 1})

    await _poll(api, mock_client, flag=0, target=0, room=0)

    # Raising the flag would make the unit regulate on a 0 °C target.
    assert _writes(mock_client) == []
    assert api.failed_restore_circuits() == [1]


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_write_back_waits_for_the_pending_write_shadow(
    _mock_ir, mock_hass, mock_client
):
    """Within the shadow a stale 0 is no new attempt; past it, it is."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)
    await _poll(api, mock_client, flag=1, target=0)
    assert len(_writes(mock_client)) == 1

    await _poll(api, mock_client, flag=1, target=0)
    assert len(_writes(mock_client)) == 1

    _expire_pending(api)
    await _poll(api, mock_client, flag=1, target=0)
    assert len(_writes(mock_client)) == 2


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_confirmed_write_back_resets_the_attempts(
    _mock_ir, mock_hass, mock_client
):
    """The reading that confirms a write-back ends the restore."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)
    await _poll(api, mock_client, flag=1, target=0)

    await _poll(api, mock_client, flag=1, target=220)

    assert api._restore_attempts == {}
    assert api._pending_writes == {}


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_gives_up_after_the_attempt_limit_and_recovers(
    _mock_ir, mock_hass, mock_client
):
    """The unit keeps dropping the target: stop writing, report, clear on recovery."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)
    for _ in range(6):
        await _poll(api, mock_client, flag=1, target=0)
        _expire_pending(api)

    assert len(_writes(mock_client)) == MAX_RESTORE_ATTEMPTS
    assert api.failed_restore_circuits() == [1]

    await _poll(api, mock_client, flag=1, target=210)
    assert api.failed_restore_circuits() == []


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_command_from_home_assistant_clears_a_failed_restore(
    _mock_ir, mock_hass, mock_client
):
    """Setting the target by hand settles the restore, as the issue asks."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)
    for _ in range(4):
        await _poll(api, mock_client, flag=1, target=0)
        _expire_pending(api)
    assert api.failed_restore_circuits() == [1]

    assert await api.set_circuit_target_temperature(1, 21.0)

    assert api.failed_restore_circuits() == []
    assert api.kept_values()["circuit1_target_temp"] == 21.0


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_circuit_2_absent_is_never_written(_mock_ir, mock_hass, mock_client):
    """Circuit 2 keys are gated out before the write-back when it is not configured."""
    api = _room_api(mock_hass, mock_client)
    api.restore_kept_values({"circuit2_thermostat": 1, "circuit2_target_temp": 22.0})
    mock_client.read_holding_registers.side_effect = [
        _make_modbus_result(0),
        _make_modbus_result(0),
        _make_modbus_result(0),
    ]

    await api.read_values(["circuit2_thermostat", "circuit2_target_temp"])
    await api.restore_lost_values()

    assert _writes(mock_client) == []


@patch("custom_components.hitachi_yutaki.api.modbus.ir")
@pytest.mark.asyncio
async def test_kept_value_changes_are_reported_once(_mock_ir, mock_hass, mock_client):
    """A new reference asks for one save; an unchanged poll does not."""
    api = _room_api(mock_hass, mock_client)
    await _poll(api, mock_client, flag=1, target=220)
    assert api.take_kept_values_changed() is True
    assert api.take_kept_values_changed() is False

    await _poll(api, mock_client, flag=1, target=220)
    assert api.take_kept_values_changed() is False
    assert api.kept_values() == {"circuit1_thermostat": 1, "circuit1_target_temp": 22.0}


def test_restore_kept_values_skips_what_it_cannot_trust(mock_hass, mock_client):
    """Unknown keys, unkept keys, lost values, odd flags and non-numbers are ignored."""
    api = _room_api(mock_hass, mock_client)
    api.restore_kept_values(
        {
            "circuit1_thermostat": 0,
            "circuit2_thermostat": 2,
            "circuit1_target_temp": 0.0,
            "circuit2_target_temp": True,
            "circuit1_current_temp": 21.0,
            "nonexistent": 1,
        }
    )

    assert api.kept_values() == {"circuit1_thermostat": 0}
