"""The external-room-sensor view of the circuit "Thermostat Available" flag."""

from __future__ import annotations

from types import MethodType
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hitachi_yutaki.api.base import HitachiApiClient
from custom_components.hitachi_yutaki.api.modbus import ModbusApiClient
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02_pre2016 import (
    AtwMbs02Pre2016RegisterMap,
)

_CONCRETE = (
    "_external_room_sensor_flag_key",
    "external_room_sensor_state",
    "external_room_sensor_enabled",
    "_external_room_sensor_circuits",
    "set_external_room_sensor",
)


def _api(supported: set[str], flags: dict[int, bool | None]) -> MagicMock:
    """Build a mock client carrying the ABC's concrete external-room-sensor methods."""
    api = MagicMock()
    for name in _CONCRETE:
        setattr(api, name, MethodType(getattr(HitachiApiClient, name), api))
    api.supports_key.side_effect = lambda key: key in supported
    api.get_circuit_thermostat.side_effect = flags.get
    return api


_2016 = {"circuit1_thermostat", "circuit2_thermostat"}
_PRE2016 = {"circuit1_thermostat"}


def test_enabled_follows_the_circuit_flag():
    """ON means the flag is 1; an unread flag is None, counted as off."""
    assert _api(_2016, {1: True}).external_room_sensor_enabled(1)
    assert not _api(_2016, {1: False}).external_room_sensor_enabled(1)
    api = _api(_2016, {1: None})
    assert api.external_room_sensor_state(1) is None
    assert not api.external_room_sensor_enabled(1)
    assert _api(_2016, {1: False, 2: True}).external_room_sensor_enabled(2)


def test_circuit_2_follows_the_global_flag_before_2016():
    """Before Line-up 2016 the flag is global, modelled on circuit 1 (#318)."""
    assert _api(_PRE2016, {1: True}).external_room_sensor_enabled(2)
    assert not _api(_PRE2016, {1: False}).external_room_sensor_enabled(2)


def _writable_api(
    supported: set[str], flags: dict[int, bool | None], circuits: set[int]
) -> MagicMock:
    api = _api(supported, flags)
    api.can_write.side_effect = lambda key: key.endswith("_current_temp")
    api.has_circuit.side_effect = lambda cid, mode: (
        cid in circuits and mode == "heating"
    )
    api.get_circuit_target_temperature.side_effect = {1: 20.0, 2: 21.0}.get
    api.set_circuit_room_temperature = AsyncMock(return_value=True)
    api.set_circuit_thermostat = AsyncMock(return_value=True)
    return api


@pytest.mark.asyncio
async def test_enabling_seeds_the_room_value_with_the_setpoint_first():
    """Room = setpoint before the flag goes up: neutral thermo-off, not a blind heat."""
    api = _writable_api(_2016, {1: False, 2: False}, {1, 2})
    assert await api.set_external_room_sensor(2, True) is True
    api.set_circuit_room_temperature.assert_awaited_once_with(2, 21.0)
    api.set_circuit_thermostat.assert_awaited_once_with(2, True)


@pytest.mark.asyncio
async def test_re_enabling_leaves_the_room_value_alone():
    """A flag already up is not re-seeded: an automation may be feeding the value."""
    api = _writable_api(_2016, {1: True}, {1})
    assert await api.set_external_room_sensor(1, True) is True
    api.set_circuit_room_temperature.assert_not_awaited()
    api.set_circuit_thermostat.assert_awaited_once_with(1, True)


@pytest.mark.asyncio
async def test_disabling_writes_the_flag_only():
    """Nothing to seed when handing regulation back to the unit."""
    api = _writable_api(_2016, {1: True}, {1})
    assert await api.set_external_room_sensor(1, False) is True
    api.set_circuit_room_temperature.assert_not_awaited()
    api.set_circuit_thermostat.assert_awaited_once_with(1, False)


@pytest.mark.asyncio
async def test_failed_seed_leaves_the_flag_down():
    """If the room value cannot be written, do not let the unit regulate on it."""
    api = _writable_api(_2016, {1: False}, {1})
    api.set_circuit_room_temperature.return_value = False
    assert await api.set_external_room_sensor(1, True) is False
    api.set_circuit_thermostat.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_setpoint_leaves_the_flag_down():
    """No setpoint to seed with means heating blind: refuse, the user retries."""
    api = _writable_api(_2016, {1: False}, {1})
    api.get_circuit_target_temperature.side_effect = None
    api.get_circuit_target_temperature.return_value = None
    assert await api.set_external_room_sensor(1, True) is False
    api.set_circuit_room_temperature.assert_not_awaited()
    api.set_circuit_thermostat.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_flag_write_after_a_seed_reports_failure():
    """The seed went through but the flag did not: the switch must say so."""
    api = _writable_api(_2016, {1: False}, {1})
    api.set_circuit_thermostat.return_value = False
    assert await api.set_external_room_sensor(1, True) is False
    api.set_circuit_room_temperature.assert_awaited_once_with(1, 20.0)


@pytest.mark.asyncio
async def test_global_flag_seeds_every_configured_circuit_before_2016():
    """Before Line-up 2016 the circuit 1 flag governs both circuits (#318)."""
    api = _writable_api(_PRE2016, {1: False}, {1, 2})
    assert await api.set_external_room_sensor(1, True) is True
    assert api.set_circuit_room_temperature.await_args_list == [
        ((1, 20.0),),
        ((2, 21.0),),
    ]
    api = _writable_api(_PRE2016, {1: False}, {1})
    await api.set_external_room_sensor(1, True)
    api.set_circuit_room_temperature.assert_awaited_once_with(1, 20.0)


@pytest.mark.asyncio
async def test_global_seed_stops_at_the_first_failure_before_2016():
    """Circuit 2 refusing the seed keeps the global flag down."""
    api = _writable_api(_PRE2016, {1: False}, {1, 2})
    api.set_circuit_room_temperature.side_effect = [True, False]
    assert await api.set_external_room_sensor(1, True) is False
    api.set_circuit_thermostat.assert_not_awaited()


def _client(register_map, system_config: int) -> ModbusApiClient:
    client = ModbusApiClient.__new__(ModbusApiClient)
    client._register_map = register_map
    client._data = {"system_config": system_config}
    return client


def test_has_room_thermostat_reads_bits_6_and_7():
    """The unit reports its own thermostats; a wired third-party one is invisible."""
    client = _client(AtwMbs02RegisterMap(), 0x0043)
    assert client.has_room_thermostat(1)
    assert not client.has_room_thermostat(2)
    client = _client(AtwMbs02Pre2016RegisterMap(), 0x0083)
    assert not client.has_room_thermostat(1)
    assert client.has_room_thermostat(2)
    assert not _client(AtwMbs02RegisterMap(), 0x0003).has_room_thermostat(1)
