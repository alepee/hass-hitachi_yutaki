"""Tests for capability-flag seeding at setup time from entry.data.

See issue #308: when the first refresh fails with gateway_not_ready, COP
services for cooling / DHW / pool must still be initialised based on the
last-known system_config persisted in entry.data.
"""

from __future__ import annotations

from custom_components.hitachi_yutaki.api.modbus import ModbusApiClient
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
)
from custom_components.hitachi_yutaki.const import (
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
)

_ATW_REGISTERS = AtwMbs02RegisterMap()


def _decode_flags(system_config: int) -> dict[str, bool]:
    """Decode a system_config value via the real api_client.decode_config().

    Mirrors what async_setup_entry does at #308 fix-time, so the result drives
    DerivedMetricsAdapter(has_cooling=…, has_dhw=…, has_pool=…) deterministically.
    """
    # We don't need a real Modbus connection: decode_config is a pure decoder.
    client = ModbusApiClient.__new__(ModbusApiClient)
    client._register_map = _ATW_REGISTERS
    decoded = client.decode_config({"system_config": system_config})
    return {
        "has_cooling": decoded["has_circuit1_cooling"]
        or decoded["has_circuit2_cooling"],
        "has_dhw": decoded["has_dhw"],
        "has_pool": decoded["has_pool"],
    }


def _build_system_config(
    *,
    circuit1_heating: bool = False,
    circuit1_cooling: bool = False,
    circuit2_heating: bool = False,
    circuit2_cooling: bool = False,
    dhw: bool = False,
    pool: bool = False,
) -> int:
    """Compose a system_config integer matching ATW-MBS-02 masks."""
    value = 0
    if circuit1_heating:
        value |= _ATW_REGISTERS.masks_circuit[
            (CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING)
        ]
    if circuit1_cooling:
        value |= _ATW_REGISTERS.masks_circuit[
            (CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING)
        ]
    if circuit2_heating:
        value |= _ATW_REGISTERS.masks_circuit[
            (CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING)
        ]
    if circuit2_cooling:
        value |= _ATW_REGISTERS.masks_circuit[
            (CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING)
        ]
    if dhw:
        value |= _ATW_REGISTERS.mask_dhw
    if pool:
        value |= _ATW_REGISTERS.mask_pool
    return value


def test_persisted_zero_yields_all_false_flags():
    """Migration path: entries without persisted system_config get all-False."""
    flags = _decode_flags(0)
    assert flags == {"has_cooling": False, "has_dhw": False, "has_pool": False}


def test_persisted_heating_only_keeps_cooling_dhw_pool_off():
    """Heating-only entry: only the heating COP service should be created."""
    cfg = _build_system_config(circuit1_heating=True)
    flags = _decode_flags(cfg)
    assert flags == {"has_cooling": False, "has_dhw": False, "has_pool": False}


def test_persisted_heating_plus_dhw_flags_dhw_on():
    """Heating + DHW: cooling COP off, DHW COP on."""
    cfg = _build_system_config(circuit1_heating=True, dhw=True)
    flags = _decode_flags(cfg)
    assert flags == {"has_cooling": False, "has_dhw": True, "has_pool": False}


def test_persisted_heating_plus_cooling_flags_cooling_on():
    """Reversible heat pump: cooling COP must be initialised at setup time."""
    cfg = _build_system_config(circuit1_heating=True, circuit1_cooling=True)
    flags = _decode_flags(cfg)
    assert flags == {"has_cooling": True, "has_dhw": False, "has_pool": False}


def test_persisted_with_pool_flags_pool_on():
    """Pool COP service must be initialised when system_config has the pool bit."""
    cfg = _build_system_config(circuit1_heating=True, pool=True)
    flags = _decode_flags(cfg)
    assert flags == {"has_cooling": False, "has_dhw": False, "has_pool": True}


def test_persisted_two_circuits_with_cooling_on_circuit2():
    """has_cooling must consider both circuits (OR semantics)."""
    cfg = _build_system_config(
        circuit1_heating=True,
        circuit2_heating=True,
        circuit2_cooling=True,
    )
    flags = _decode_flags(cfg)
    assert flags["has_cooling"] is True


def test_persisted_full_capability_unit():
    """Full reversible unit with DHW and pool: all COP services initialised."""
    cfg = _build_system_config(
        circuit1_heating=True,
        circuit1_cooling=True,
        circuit2_heating=True,
        circuit2_cooling=True,
        dhw=True,
        pool=True,
    )
    flags = _decode_flags(cfg)
    assert flags == {"has_cooling": True, "has_dhw": True, "has_pool": True}
