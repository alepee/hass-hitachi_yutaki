"""Register codecs: how a 16-bit register word maps to a value, both ways.

Every :class:`RegisterDefinition` declares one codec. ``decode`` turns the raw
word read from the gateway into the value the integration stores; ``encode``
turns a value back into the word to write. A raw word is never consumed or
written as is (#533).

Contract: for every value ``encode`` accepts, ``decode(encode(value)) ==
value``. ``encode`` raises ``ValueError`` (``TypeError`` for a non-number) for
a value the register cannot hold.
``decode`` returns ``None`` when the word carries no value (e.g. ``0xFFFF`` on
an unsigned register, or a code outside a closed domain).

The codec is picked from the register's documented type:

- a quantity (frequency, opening, setpoint in degrees): :data:`UNSIGNED`;
- a signed quantity, marked (*1) in the gateway documentation: :data:`SIGNED`;
- a quantity in tenths, marked (*3) where it applies: :data:`TENTHS`;
- a closed list of values (switch, mode, state, model): an :class:`EnumCodec`,
  so an undocumented word reads as unknown instead of as a value.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from ....const import OTCCalculationMethod

# The word an unsigned register returns when it carries no value. On a signed
# register the same word is -1, a valid reading (#533).
NOT_EXPOSED = 0xFFFF


class RegisterCodec(Protocol):
    """Two-way conversion between a register word and a value."""

    def decode(self, raw: int) -> Any:
        """Return the value of a raw 16-bit word, or None when it has none."""

    def encode(self, value: Any) -> int:
        """Return the raw 16-bit word for ``value``, raising ValueError/TypeError."""


def _whole(value: Any) -> int:
    """Return ``value`` as an int, raising when it is not a whole number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"not a number: {value!r}")
    raw = int(value)
    if raw != value:
        raise ValueError(f"not a whole number: {value!r}")
    return raw


@dataclass(frozen=True)
class Unsigned:
    """An unsigned quantity; ``0xFFFF`` carries no value."""

    def decode(self, raw: int) -> int | None:
        """Return the word, or None for ``0xFFFF``."""
        return None if raw == NOT_EXPOSED else raw

    def encode(self, value: Any) -> int:
        """Return the word for a whole value in 0~65534."""
        raw = _whole(value)
        if not 0 <= raw < NOT_EXPOSED:
            raise ValueError(f"out of unsigned range: {value!r}")
        return raw


@dataclass(frozen=True)
class Signed:
    """A signed quantity in two's complement; ``0xFFFF`` is -1 (#533)."""

    def decode(self, raw: int) -> int:
        """Return the two's complement value of the word."""
        return raw - 0x10000 if raw > 0x7FFF else raw

    def encode(self, value: Any) -> int:
        """Return the two's complement word for a whole value."""
        raw = _whole(value)
        if not -0x8000 <= raw <= 0x7FFF:
            raise ValueError(f"out of signed range: {value!r}")
        return raw & 0xFFFF


@dataclass(frozen=True)
class Scaled:
    """An unsigned quantity stored as ``value * factor``; ``0xFFFF`` is none.

    Tenths of a degree, of a cubic metre per hour, of an ampere; pressures in
    hundredths of MPa, which are tenths of a bar.
    """

    factor: int

    def decode(self, raw: int) -> float | None:
        """Return the scaled value, or None for ``0xFFFF``."""
        return None if raw == NOT_EXPOSED else raw / self.factor

    def encode(self, value: Any) -> int:
        """Return the word for ``value``, rounded to the register resolution."""
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError(f"not a number: {value!r}")
        raw = round(value * self.factor)
        if not 0 <= raw < NOT_EXPOSED:
            raise ValueError(f"out of range: {value!r}")
        return raw


@dataclass(frozen=True, eq=False)
class EnumCodec:
    """A closed list of documented words, each mapped to a value.

    A word outside the list decodes to ``unknown``; encoding a value outside
    the list raises, so a bad command is refused instead of written.
    """

    values: Mapping[int, Any]
    unknown: Any = None
    _raws: Mapping[Any, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Index the words by value for ``encode``."""
        raws = {value: raw for raw, value in self.values.items()}
        if len(raws) != len(self.values):
            raise ValueError("an EnumCodec maps each value to one word")
        object.__setattr__(self, "_raws", raws)

    def decode(self, raw: int) -> Any:
        """Return the value of a documented word, else ``unknown``."""
        return self.values.get(raw, self.unknown)

    def encode(self, value: Any) -> int:
        """Return the word of a documented value."""
        if isinstance(value, bool):
            value = int(value)
        try:
            return self._raws[value]
        except (KeyError, TypeError):
            raise ValueError(f"not a documented value: {value!r}") from None


@dataclass(frozen=True)
class Prefixed:
    """A numeric code exposed as a translation key (``alarm_code_42``)."""

    prefix: str

    def decode(self, raw: int) -> str | None:
        """Return the key of the code, or None for ``0xFFFF``."""
        return None if raw == NOT_EXPOSED else f"{self.prefix}{raw}"

    def encode(self, value: Any) -> int:
        """Return the code of a key."""
        if not isinstance(value, str) or not value.startswith(self.prefix):
            raise ValueError(f"not a {self.prefix} key: {value!r}")
        raw = int(value.removeprefix(self.prefix))
        if not 0 <= raw < NOT_EXPOSED:
            raise ValueError(f"out of range: {value!r}")
        return raw


def choice(*raws: int) -> EnumCodec:
    """Return a codec for a register whose value is one of ``raws``, as is."""
    return EnumCodec({raw: raw for raw in raws})


UNSIGNED = Unsigned()
SIGNED = Signed()
TENTHS = Scaled(10)

# 0 / 1 registers: run/stop, enable flags, eco/comfort.
SWITCH = choice(0, 1)
# "LCD Central Mode": 0 local, 1 air, 2 water, 3 full.
CENTRAL_CONTROL_MODE = choice(0, 1, 2, 3)

SYSTEM_STATE = EnumCodec(
    {0: "synchronized", 1: "desynchronized", 2: "initializing"}, unknown="unknown"
)

OPERATION_STATE = EnumCodec(
    {
        raw: f"operation_state_{name}"
        for raw, name in enumerate(
            (
                "off",
                "cool_demand_off",
                "cool_thermo_off",
                "cool_thermo_on",
                "heat_demand_off",
                "heat_thermo_off",
                "heat_thermo_on",
                "dhw_off",
                "dhw_on",
                "pool_off",
                "pool_on",
                "alarm",
            )
        )
    },
    unknown="operation_state_unknown",
)

ALARM_CODE = Prefixed("alarm_code_")

OTC_METHOD_HEATING = EnumCodec(
    {
        0: OTCCalculationMethod.DISABLED,
        1: OTCCalculationMethod.POINTS,
        2: OTCCalculationMethod.GRADIENT,
        3: OTCCalculationMethod.FIX,
    }
)
# Cooling has no Gradient option: 0 disabled, 1 points, 2 fix.
OTC_METHOD_COOLING = EnumCodec(
    {
        0: OTCCalculationMethod.DISABLED,
        1: OTCCalculationMethod.POINTS,
        2: OTCCalculationMethod.FIX,
    }
)

# Unit model ids shared by every gateway; each map accepts its own subset.
UNIT_MODELS = {
    0: "yutaki_s",
    1: "yutaki_s_combi",
    2: "yutaki_s80",
    3: "yutaki_m",
    4: "yutaki_sc_lite",
    5: "yutampo_r32",
    6: "ycc",
}


def unit_model(*ids: int) -> EnumCodec:
    """Return the unit model codec of a gateway documenting ``ids``."""
    return EnumCodec({i: UNIT_MODELS[i] for i in ids}, unknown="unknown")
