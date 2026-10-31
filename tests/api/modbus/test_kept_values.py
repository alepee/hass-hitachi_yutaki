"""Tests for the write-back plan of values a reboot clears (#511).

A fictitious map with neutral keys: the engine knows nothing about what the
values mean, only their ``Keep`` declarations.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.hitachi_yutaki.api.modbus.kept_values import (
    MAX_RESTORE_ATTEMPTS,
    KeptValues,
)
from custom_components.hitachi_yutaki.api.modbus.registers import (
    Keep,
    RegisterDefinition,
)

REGISTERS = {
    "enable": RegisterDefinition(1, keep=Keep(valid_range=(0, 1))),
    "setpoint": RegisterDefinition(
        2, keep=Keep(valid_range=(5, 35), while_on="enable")
    ),
    "copy": RegisterDefinition(3, keep=Keep(while_on="enable", seed_from="setpoint")),
    "other": RegisterDefinition(4),
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


def test_gate_alone_goes_back_at_once():
    """Dependents that survived leave nothing to wait for."""
    kept = _kept(enable=1, setpoint=20)
    assert _step(kept, {"enable": 0, "setpoint": 20, "copy": 19}) == [("enable", 1)]


def test_dependents_left_alone_while_their_gate_is_off():
    """A gate turned off on purpose (reference 0) leaves its dependents alone."""
    kept = _kept(enable=0, setpoint=20)
    assert _step(kept, {"enable": 0, "setpoint": 0, "copy": 0}) == []
    assert kept.failed is False


def test_gate_waits_while_a_dependent_went_unread():
    """An unread dependent has an unknown state: no write, no report."""
    kept = _kept(enable=1, setpoint=20)
    assert _step(kept, {"enable": 0, "copy": 19}) == []
    assert kept.failed is False


def test_gate_with_an_unrestorable_dependent_is_reported():
    """No reference for the setpoint: the gate stays down and the failure shows."""
    kept = _kept(enable=1)
    assert _step(kept, {"enable": 0, "setpoint": 0, "copy": 0}) == []
    assert kept.failed is True

    # The obstacle goes (setpoint set by hand): the report clears, the gate goes back.
    assert _step(kept, {"enable": 0, "setpoint": 21, "copy": 21}) == [("enable", 1)]
    assert kept.failed is False


def test_attempts_are_capped_then_retried_on_demand():
    """Three write-backs, then a failure; a retry gives a fresh set."""
    kept = _kept(enable=1, setpoint=20)
    lost = {"enable": 1, "setpoint": 0, "copy": 19}
    writes = [w for _ in range(5) for w in _step(kept, lost)]
    assert writes == [("setpoint", 20)] * MAX_RESTORE_ATTEMPTS
    assert kept.failed is True

    kept.retry()
    assert kept.failed is False
    assert _step(kept, lost) == [("setpoint", 20)]


def test_write_from_home_assistant_settles_and_becomes_the_reference():
    """A command is the new reference and clears the failure; a write-back is not."""
    kept = _kept(enable=1, setpoint=20)
    for _ in range(4):
        _step(kept, {"enable": 1, "setpoint": 0, "copy": 19})
    assert kept.failed is True

    kept.written("setpoint", 20, by_restore=True)
    assert kept.failed is True
    kept.written("setpoint", 22, by_restore=False)
    assert kept.failed is False
    assert kept.snapshot()["setpoint"] == 22
    assert kept.wanted("setpoint", 20) is False


def test_listener_notified_on_reference_changes_only():
    """The persistence hook fires on a new reference, not on a repeat."""
    kept = _kept()
    listener = MagicMock()
    kept.listen(listener)

    _step(kept, {"enable": 1, "setpoint": 20, "copy": 19})
    _step(kept, {"enable": 1, "setpoint": 20, "copy": 19})
    kept.written("copy", 21, by_restore=False)

    assert listener.call_count == 2


def test_load_skips_what_it_cannot_trust():
    """Unknown, unkept, seeded, out-of-range and non-integer raw values are ignored."""
    kept = _kept(enable=0.5, setpoint=0, copy=20, other=1, unknown=1, x="1")
    assert kept.snapshot() == {}
    kept.load({"enable": 0, "setpoint": 21})
    assert kept.snapshot() == {"enable": 0, "setpoint": 21}
