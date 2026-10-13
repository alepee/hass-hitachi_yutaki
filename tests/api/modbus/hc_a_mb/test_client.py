"""Tests for the HC-A(16/64)MB client: unit table and unit binding (#476)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pymodbus.exceptions import ModbusException
import pytest

from custom_components.hitachi_yutaki.api.base import UnitBindingStatus
from custom_components.hitachi_yutaki.api.modbus import ModbusApiClient
from custom_components.hitachi_yutaki.api.modbus.hc_a_mb import HcAMbApiClient
from custom_components.hitachi_yutaki.api.modbus.registers.hc_a_mb import (
    HcAMbRegisterMap,
)

EMPTY = [0, 255, 255, 255]
# Dump A from #476: 2x Yutaki S, 2x Yutampo R32.
DUMP_A = [1, 0, 0, 0, 1, 1, 1, 1, 1, 5, 6, 2, 1, 7, 8, 3] + EMPTY * 12
# Yutaki S #1 (0, 0) absent at enumeration: every unit above it shifts down.
SHIFTED = [1, 1, 1, 0, 1, 5, 6, 1, 1, 7, 8, 2] + EMPTY * 13


def _registers_result(registers: list[int]) -> MagicMock:
    result = MagicMock()
    result.isError.return_value = False
    result.registers = registers
    return result


@pytest.fixture
def mock_client():
    """Create a mock pymodbus client serving the unit table."""
    client = MagicMock()
    client.is_socket_open.return_value = True
    return client


@pytest.fixture
def api_client(mock_client):
    """Create an HcAMbApiClient bound to slot 2 with mocked I/O."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda f: f())
    with patch.object(ModbusApiClient, "__init__", lambda *args, **kwargs: None):
        api = HcAMbApiClient()
    api._hass = hass
    api._client = mock_client
    api._slave = 1
    api._register_map = HcAMbRegisterMap(unit_id=2)
    return api


def _serve(mock_client, registers: list[int]) -> None:
    """Serve ``registers`` as the unit table, sliced like the gateway would."""

    def read(address: int, count: int, **_kwargs):
        start = address - 200
        return _registers_result(registers[start : start + count])

    mock_client.read_input_registers.side_effect = read


def _entry(unit_id: int, outdoor_cycle=None, indoor_address=None) -> dict:
    data = {"unit_id": unit_id}
    if outdoor_cycle is not None:
        data["outdoor_cycle"] = outdoor_cycle
    if indoor_address is not None:
        data["indoor_address"] = indoor_address
    return data


# --- Unit table ---


@pytest.mark.asyncio
async def test_read_unit_table_decodes_whole_table(api_client, mock_client):
    """One FC04 read of 64 registers at 200 decodes the 16 slots."""
    _serve(mock_client, DUMP_A)

    table = await api_client.async_read_unit_table()

    kwargs = mock_client.read_input_registers.call_args.kwargs
    assert (kwargs["address"], kwargs["count"]) == (200, 64)
    assert [s.identity for s in table if s.is_valid] == [(0, 0), (1, 1), (5, 6), (7, 8)]
    assert all(s.is_empty for s in table[4:])


@pytest.mark.asyncio
async def test_read_unit_table_single_slot(api_client, mock_client):
    """A single slot is read at 200 + slot * 4 and keeps its index."""
    _serve(mock_client, DUMP_A)

    table = await api_client.async_read_unit_table(2, 1)

    kwargs = mock_client.read_input_registers.call_args.kwargs
    assert (kwargs["address"], kwargs["count"]) == (208, 4)
    assert (table[0].slot, table[0].identity) == (2, (5, 6))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [
        MagicMock(isError=MagicMock(return_value=True)),
        _registers_result([1, 5, 6]),
    ],
    ids=["modbus_error", "short_read"],
)
async def test_read_unit_table_bad_result_returns_none(api_client, mock_client, result):
    """An error or truncated result yields None."""
    mock_client.read_input_registers.return_value = result

    assert await api_client.async_read_unit_table(0, 1) is None


@pytest.mark.asyncio
async def test_read_unit_table_exception_returns_none(api_client, mock_client):
    """A ModbusException during the read yields None."""
    mock_client.read_input_registers.side_effect = ModbusException("boom")

    assert await api_client.async_read_unit_table() is None


# --- Unit binding ---


@pytest.mark.asyncio
async def test_bind_follows_a_unit_that_moved(api_client, mock_client):
    """The client rebinds to the slot now holding its (Ou, Iu) pair."""
    _serve(mock_client, SHIFTED)

    binding = await api_client.async_bind_unit(_entry(2, 5, 6))

    assert binding.status is UnitBindingStatus.BOUND
    assert binding.updates == {"unit_id": 1, "outdoor_cycle": 5, "indoor_address": 6}
    assert api_client.register_map.unit_id == 1


@pytest.mark.asyncio
async def test_bind_missing_unit_never_reads_the_old_slot(api_client, mock_client):
    """An absent unit is reported, not replaced by the unit in its old slot."""
    _serve(mock_client, SHIFTED)

    binding = await api_client.async_bind_unit(_entry(0, 0, 0))

    assert binding.status is UnitBindingStatus.MISSING
    assert binding.placeholders == {"outdoor_cycle": "0", "indoor_address": "0"}
    assert api_client.register_map.unit_id == 2


@pytest.mark.asyncio
async def test_bind_waits_for_a_settling_table(api_client, mock_client):
    """A table mid re-enumeration is retried, not reported."""
    _serve(mock_client, [1, 1, 1, 0, 1, 0, 0, 255] + EMPTY * 14)

    binding = await api_client.async_bind_unit(_entry(0, 0, 0))

    assert binding.status is UnitBindingStatus.SETTLING


@pytest.mark.asyncio
async def test_bind_legacy_entry_records_its_indoor_address(api_client, mock_client):
    """Entries created after #353 but before #476 self-heal Iu from their cycle."""
    _serve(mock_client, DUMP_A)

    binding = await api_client.async_bind_unit(_entry(3, 7))

    assert binding.updates == {"unit_id": 3, "outdoor_cycle": 7, "indoor_address": 8}


@pytest.mark.asyncio
async def test_bind_pre_353_entry_adopts_its_slot(api_client, mock_client):
    """Entries with no identity at all take the unit in their stored slot."""
    _serve(mock_client, DUMP_A)

    binding = await api_client.async_bind_unit(_entry(2))

    assert binding.updates == {"unit_id": 2, "outdoor_cycle": 5, "indoor_address": 6}


@pytest.mark.asyncio
async def test_bind_pre_353_entry_on_an_empty_slot_is_unverified(
    api_client, mock_client
):
    """Nothing to compare against: keep the previous best-effort behaviour."""
    _serve(mock_client, DUMP_A)

    binding = await api_client.async_bind_unit(_entry(6))

    assert binding.status is UnitBindingStatus.UNVERIFIED


@pytest.mark.asyncio
async def test_bind_unreadable_table_is_unverified(api_client, mock_client):
    """An unreadable table leaves the client on its stored slot."""
    mock_client.read_input_registers.side_effect = ModbusException("boom")

    binding = await api_client.async_bind_unit(_entry(2, 5, 6))

    assert binding.status is UnitBindingStatus.UNVERIFIED
    assert api_client.register_map.unit_id == 2


# --- Unit verification ---


@pytest.mark.asyncio
async def test_verify_unbound_client_passes(api_client, mock_client):
    """Before any binding there is nothing to verify."""
    assert await api_client.async_verify_unit() is True
    mock_client.read_input_registers.assert_not_called()


@pytest.mark.asyncio
async def test_verify_detects_a_unit_that_moved(api_client, mock_client):
    """True while the bound slot holds the unit, False once another unit sits there."""
    _serve(mock_client, DUMP_A)
    await api_client.async_bind_unit(_entry(2, 5, 6))
    assert await api_client.async_verify_unit() is True

    _serve(mock_client, SHIFTED)
    assert await api_client.async_verify_unit() is False


@pytest.mark.asyncio
async def test_verify_unreadable_slot_is_inconclusive(api_client, mock_client):
    """An unreadable slot is not a move."""
    _serve(mock_client, DUMP_A)
    await api_client.async_bind_unit(_entry(2, 5, 6))
    mock_client.read_input_registers.side_effect = ModbusException("boom")

    assert await api_client.async_verify_unit() is None


@pytest.mark.asyncio
async def test_verify_still_runs_when_the_table_was_unreadable_at_setup(
    api_client, mock_client
):
    """An unverified binding keeps the stored pair as the runtime reference."""
    mock_client.read_input_registers.side_effect = ModbusException("busy")
    binding = await api_client.async_bind_unit(_entry(2, 5, 6))
    assert binding.status is UnitBindingStatus.UNVERIFIED

    _serve(mock_client, SHIFTED)  # slot 2 now holds (7, 8)
    assert await api_client.async_verify_unit() is False
