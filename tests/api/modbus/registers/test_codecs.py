"""Tests for the register codecs and the codec contract of every map (#533)."""

from __future__ import annotations

import pytest

from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    ALARM_CODE,
    OPERATION_STATE,
    OTC_METHOD_HEATING,
    SWITCH,
    SYSTEM_STATE,
    AtwMbs02RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02_pre2016 import (
    AtwMbs02Pre2016RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.codecs import (
    SIGNED,
    TENTHS,
    UNSIGNED,
    EnumCodec,
)
from custom_components.hitachi_yutaki.api.modbus.registers.hc_a_mb import (
    HcAMbRegisterMap,
)
from custom_components.hitachi_yutaki.const import OTCCalculationMethod

MAPS = [AtwMbs02RegisterMap(), AtwMbs02Pre2016RegisterMap(), HcAMbRegisterMap()]


class TestUnsigned:
    """Quantities: 0xFFFF carries no value."""

    def test_decode(self):
        """A word is its value, except 0xFFFF."""
        assert UNSIGNED.decode(350) == 350
        assert UNSIGNED.decode(0xFFFF) is None

    def test_encode(self):
        """Only whole values in range are written; nothing is truncated."""
        assert UNSIGNED.encode(45) == 45
        assert UNSIGNED.encode(45.0) == 45
        for bad in (45.5, -1, 0xFFFF):
            with pytest.raises(ValueError):
                UNSIGNED.encode(bad)
        with pytest.raises(TypeError):
            UNSIGNED.encode("45")


class TestSigned:
    """Signed quantities (*1): two's complement, 0xFFFF is -1 (#533)."""

    def test_decode(self):
        """0xFFFF is -1 and its neighbours decode around it."""
        assert SIGNED.decode(0) == 0
        assert SIGNED.decode(25) == 25
        assert SIGNED.decode(0xFFFF) == -1
        assert SIGNED.decode(0xFFFE) == -2
        assert SIGNED.decode(0xFFFB) == -5
        assert SIGNED.decode(0xFF81) == -127

    def test_encode(self):
        """Negative values are written in two's complement."""
        assert SIGNED.encode(-1) == 0xFFFF
        assert SIGNED.encode(-127) == 0xFF81
        with pytest.raises(ValueError):
            SIGNED.encode(40000)


class TestTenths:
    """Tenths of a unit; pressures in hundredths of MPa are tenths of a bar."""

    def test_decode(self):
        """A word is a tenth of the value, except 0xFFFF."""
        assert TENTHS.decode(250) == 25.0
        assert TENTHS.decode(510) == 51.0
        assert TENTHS.decode(0xFFFF) is None

    def test_encode_rounds(self):
        """21.3 °C is 213, not the 212 a truncation gave."""
        assert TENTHS.encode(21.3) == 213
        assert TENTHS.encode(22.5) == 225


class TestEnumCodec:
    """Closed lists: an undocumented word is unknown, a bad value is refused."""

    def test_switch(self):
        """0/1 registers decode as is and refuse anything else."""
        assert SWITCH.decode(1) == 1
        assert SWITCH.decode(0xFFFF) is None
        assert SWITCH.encode(True) == 1
        with pytest.raises(ValueError):
            SWITCH.encode(2)

    def test_states(self):
        """States decode to their key, unknown words to the unknown key."""
        assert SYSTEM_STATE.decode(0) == "synchronized"
        assert SYSTEM_STATE.decode(0xFFFF) == "unknown"
        assert OPERATION_STATE.decode(6) == "operation_state_heat_thermo_on"
        assert OPERATION_STATE.decode(67) == "operation_state_unknown"

    def test_otc_method_refuses_unknown_value(self):
        """An invalid method was written as 0 (disabled); it now fails."""
        assert OTC_METHOD_HEATING.encode(OTCCalculationMethod.GRADIENT) == 2
        with pytest.raises(ValueError):
            OTC_METHOD_HEATING.encode("bogus")

    def test_one_word_per_value(self):
        """Two words for one value make encode ambiguous unless writes says."""
        with pytest.raises(ValueError, match="give writes"):
            EnumCodec({0: "a", 1: "a"})
        codec = EnumCodec({0: "a", 1: "a"}, writes={"a": 1})
        assert codec.decode(0) == "a"
        assert codec.encode("a") == 1

    def test_writes_must_read_back(self):
        """A write that would read back as another value is refused at build."""
        with pytest.raises(ValueError, match="reads back otherwise"):
            EnumCodec({0: "a", 1: "b"}, writes={"a": 1})
        with pytest.raises(ValueError, match="reads back otherwise"):
            EnumCodec({0: "a"}, writes={"b": 7})

    def test_writes_can_be_a_subset(self):
        """A value that can be read but not commanded is refused on write."""
        codec = EnumCodec({0: "cool", 1: "heat", 2: "auto"}, writes={"cool": 0})
        assert codec.decode(2) == "auto"
        with pytest.raises(ValueError):
            codec.encode("auto")


class TestPrefixed:
    """Alarm codes are exposed as translation keys."""

    def test_round_trip(self):
        """A code maps to its key and back; 0xFFFF is no alarm reading."""
        assert ALARM_CODE.decode(3) == "alarm_code_3"
        assert ALARM_CODE.encode("alarm_code_3") == 3
        assert ALARM_CODE.decode(0xFFFF) is None


@pytest.mark.parametrize("register_map", MAPS, ids=lambda m: type(m).__name__)
def test_every_register_round_trips(register_map):
    """Every value a register reads, when writable, reads back as written.

    This is the codec contract the write path, the read-back shadow and the
    reboot restore rely on. Sampled words: the low range, the signed boundary
    and the top of the range.
    """
    words = [*range(16), 100, 255, 350, 0x7FFF, 0x8000, 0xFF81, 0xFFFE, 0xFFFF]
    for key, reg in register_map.all_registers.items():
        for definition in (reg, reg.fallback):
            if definition is None:
                continue
            for raw in words:
                value = definition.codec.decode(raw)
                if value is None or value in ("unknown", "operation_state_unknown"):
                    continue
                try:
                    encoded = definition.codec.encode(value)
                except ValueError:
                    continue  # readable but not writable (e.g. HC-A auto mode)
                assert definition.codec.decode(encoded) == value, (key, raw)


@pytest.mark.parametrize("register_map", MAPS, ids=lambda m: type(m).__name__)
def test_writable_registers_encode_their_reading(register_map):
    """A value read from a writable register can be written back as is."""
    for key in register_map.writable_keys:
        codec = register_map.all_registers[key].codec
        value = codec.decode(1)
        if value is not None:
            assert codec.decode(codec.encode(value)) == value, key
