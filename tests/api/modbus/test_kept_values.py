"""Tests for the write-back plan of values a reboot clears (#511).

A fictitious map with neutral keys guards the one contract the client
scenarios cannot: the engine knows nothing about what the values mean, only
their ``Keep`` declarations. Behaviour is owned by the Modbus client tests.
"""

from __future__ import annotations

from custom_components.hitachi_yutaki.api.modbus.kept_values import KeptValues
from custom_components.hitachi_yutaki.api.modbus.registers import (
    Keep,
    RegisterDefinition,
)
from custom_components.hitachi_yutaki.api.modbus.registers.codecs import UNSIGNED

REGISTERS = {
    "enable": RegisterDefinition(1, UNSIGNED, keep=Keep(valid_range=(0, 1))),
    "setpoint": RegisterDefinition(
        2, UNSIGNED, keep=Keep(valid_range=(5, 35), while_on="enable")
    ),
    "copy": RegisterDefinition(
        3, UNSIGNED, keep=Keep(while_on="enable", seed_from="setpoint")
    ),
    "other": RegisterDefinition(4, UNSIGNED),
}


def _kept(**references) -> KeptValues:
    kept = KeptValues(REGISTERS, set(REGISTERS))
    kept.load(references)
    return kept


def _step(kept: KeptValues, data: dict, pending=()) -> list[tuple[str, object]]:
    """One read then one plan, as the client does on every poll."""
    kept.track(data, data)
    return kept.plan(data, set(pending))


def test_nothing_planned_while_values_read_right():
    """Readings that are not lost only refresh the references."""
    kept = _kept()
    assert _step(kept, {"enable": 1, "setpoint": 20, "copy": 19}) == []
    assert kept.snapshot() == {"enable": 1, "setpoint": 20}


def test_everything_lost_goes_back_in_three_confirmed_steps():
    """Seeded copy, then its source, then the gate, each once the previous reads right."""
    kept = _kept(enable=1, setpoint=20)

    assert _step(kept, {"enable": 0, "setpoint": 0, "copy": 0}) == [("copy", 20)]
    assert _step(kept, {"enable": 0, "setpoint": 0}, pending={"copy"}) == []
    assert _step(kept, {"enable": 0, "setpoint": 0, "copy": 20}) == [("setpoint", 20)]
    assert _step(kept, {"enable": 0, "setpoint": 20, "copy": 20}) == [("enable", 1)]


def test_load_skips_what_it_cannot_trust():
    """Unknown, unkept, seeded, out-of-range, bool and non-integer raw values are ignored."""
    kept = _kept(enable=0.5, setpoint=0, copy=20, other=1, unknown=1)
    kept.load({"enable": True})  # In range as 1: only the bool guard refuses it.
    kept.load({"enable": None})  # Only the number guard refuses it (JSON null).
    assert kept.snapshot() == {}
    kept.load({"enable": 0, "setpoint": 21})
    assert kept.snapshot() == {"enable": 0, "setpoint": 21}
