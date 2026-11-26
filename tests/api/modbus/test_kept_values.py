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
from custom_components.hitachi_yutaki.api.modbus.registers.codecs import (
    HALF_DEGREE,
    UNSIGNED,
)

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


def test_load_keeps_a_reference_at_its_write_resolution():
    """A reference off the write resolution is loaded as it will be written (#540).

    A room setpoint of 21.3 persisted before half-degree writes is restored as
    21.5, the value the register reads back after the write-back.
    """
    registers = {
        "room": RegisterDefinition(1, HALF_DEGREE, keep=Keep(valid_range=(5.0, 35.0)))
    }
    kept = KeptValues(registers, set(registers))
    kept.load({"room": 21.3})
    assert kept.snapshot() == {"room": 21.5}
    kept.load({"room": 35.2})  # Written as 35.0: inside the range once rounded.
    assert kept.snapshot() == {"room": 35.0}


def test_reference_read_off_the_write_resolution_settles_once_written():
    """A reading of 21.3 is written back as 21.5 once, then read right (#540)."""
    registers = {
        "room": RegisterDefinition(1, HALF_DEGREE, keep=Keep(valid_range=(5.0, 35.0)))
    }
    kept = KeptValues(registers, set(registers))
    assert _step(kept, {"room": 21.3}) == []
    assert _step(kept, {"room": 0}) == [("room", 21.3)]
    kept.written("room", HALF_DEGREE.decode(HALF_DEGREE.encode(21.3)), by_restore=True)
    assert kept.snapshot() == {"room": 21.5}
    assert _step(kept, {"room": 21.5}) == []


def test_a_command_after_the_plan_withdraws_the_write_back():
    """A write from Home Assistant since the plan wins, seeded values included."""
    kept = _kept(enable=1, setpoint=20)
    assert _step(kept, {"enable": 1, "setpoint": 20, "copy": 0}) == [("copy", 20)]
    assert kept.wanted("copy", 20)

    kept.written("copy", 18, by_restore=False)

    assert not kept.wanted("copy", 20)


def test_a_write_back_is_wanted_once():
    """Performed, the write-back is done with; a stale plan entry is not wanted."""
    kept = _kept(enable=1, setpoint=20)
    assert _step(kept, {"enable": 1, "setpoint": 0, "copy": 19}) == [("setpoint", 20)]
    assert not kept.wanted("setpoint", 21)

    kept.written("setpoint", 20, by_restore=True)

    assert not kept.wanted("setpoint", 20)


def test_a_write_from_home_assistant_settling_a_failure_notifies_at_once():
    """Setting a value that would not go back clears its failure without a read.

    The settled listener hears it, so the failure report follows at once
    instead of lingering until the next poll. The reference listener does not:
    the written value equals the reference.
    """
    kept = _kept(enable=1, setpoint=20)
    lost = {"enable": 1, "setpoint": 0, "copy": 20}
    for _ in range(3):
        assert _step(kept, lost) == [("setpoint", 20)]
    assert _step(kept, lost) == []
    assert kept.failed

    settled, references = [], []
    kept.listen_settled(lambda: settled.append(True))
    kept.listen(lambda: references.append(True))
    kept.written("setpoint", 20, by_restore=False)

    assert not kept.failed
    assert settled == [True]
    assert references == []


def test_a_write_back_does_not_settle_a_failure():
    """A write-back is not the user's word: it neither settles nor notifies."""
    kept = _kept(enable=1, setpoint=20)
    lost = {"enable": 1, "setpoint": 0, "copy": 20}
    for _ in range(4):
        _step(kept, lost)
    calls = []
    kept.listen_settled(lambda: calls.append(True))
    kept.written("setpoint", 20, by_restore=True)

    assert kept.failed
    assert calls == []


def test_a_command_between_the_read_and_the_plan_is_not_overwritten():
    """A write from Home Assistant after the read found the value lost wins.

    The read queues the write-back of the old reference; a command landing
    before the plan (e.g. while the unit is being verified after a reboot)
    must withdraw it, or the plan would overwrite the fresh command with the
    stale reference.
    """
    kept = _kept(enable=1, setpoint=20)
    data = {"enable": 1, "setpoint": 0, "copy": 19}
    kept.track(data, data)

    kept.written("setpoint", 22, by_restore=False)
    data["setpoint"] = 22  # The client publishes the written value at once.

    assert kept.plan(data, {"setpoint"}) == []
    assert kept.snapshot()["setpoint"] == 22
