"""Tests for the ``Keep`` declaration contract of register maps (#511)."""

from __future__ import annotations

import pytest

from custom_components.hitachi_yutaki.api.modbus.registers import (
    Keep,
    RegisterDefinition,
    validate_kept_registers,
)
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02_pre2016 import (
    AtwMbs02Pre2016RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.hc_a_mb import (
    HcAMbRegisterMap,
)


@pytest.mark.parametrize(
    "register_map",
    [AtwMbs02RegisterMap(), AtwMbs02Pre2016RegisterMap(), HcAMbRegisterMap()],
)
def test_every_shipped_map_declares_valid_kept_values(register_map):
    """An invalid declaration would only surface as a setup error on user installs."""
    validate_kept_registers(register_map.all_registers, register_map.writable_keys)


@pytest.mark.parametrize(
    ("declarations", "problem"),
    [
        ({"a": Keep(while_on="missing")}, "while_on must name another kept register"),
        ({"a": Keep(while_on="a")}, "while_on must name another kept register"),
        (
            {"a": Keep(while_on="b"), "b": None},
            "while_on must name another kept register",
        ),
        (
            {"a": Keep(while_on="b"), "b": Keep(while_on="c"), "c": Keep()},
            "while_on target must depend on nothing",
        ),
        (
            {"a": Keep(seed_from="b", while_on="c"), "b": Keep(), "c": Keep()},
            "seed_from source must share while_on",
        ),
        (
            {
                "a": Keep(seed_from="b", while_on="c"),
                "b": Keep(seed_from="a", while_on="c"),
                "c": Keep(),
            },
            "seed_from source must share while_on",
        ),
        (
            {"a": Keep(seed_from="b"), "b": Keep(), "c": Keep(while_on="b")},
            "seed_from source must share while_on",
        ),
        ({"a": Keep(seed_from="missing")}, "seed_from must name another kept register"),
        (
            {"a": Keep(while_on="b"), "b": Keep(seed_from="c"), "c": Keep()},
            "while_on target must depend on nothing",
        ),
    ],
)
def test_invalid_kept_declarations_are_rejected(declarations, problem):
    """Dangling, self, chained or cyclic references fail at load, not in production."""
    registers = {
        key: RegisterDefinition(1000 + i, keep=keep)
        for i, (key, keep) in enumerate(declarations.items())
    }
    with pytest.raises(ValueError, match=problem):
        validate_kept_registers(registers, set(registers))


def test_kept_register_must_be_writable_and_serializable():
    """A value the client cannot write back, or only as the wrong raw value, is refused."""
    unwritable = {"a": RegisterDefinition(1000, keep=Keep())}
    with pytest.raises(ValueError, match="must be writable"):
        validate_kept_registers(unwritable, set())

    unserializable = {"a": RegisterDefinition(1000, deserializer=float, keep=Keep())}
    with pytest.raises(ValueError, match="needs a serializer"):
        validate_kept_registers(unserializable, {"a"})
