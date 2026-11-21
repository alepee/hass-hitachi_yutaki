"""Quantities stored scaled (tenths, marked (*3)); ``0xFFFF`` carries no value."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .protocol import NOT_EXPOSED


@dataclass(frozen=True)
class Scaled:
    """An unsigned quantity stored as ``value * factor``; ``0xFFFF`` is none.

    Tenths of a degree, of a cubic metre per hour, of an ampere; pressures in
    hundredths of MPa, which are tenths of a bar.

    ``step`` is the write resolution in raw units, for a register the unit
    applies more coarsely than it stores: a room temperature is stored in
    tenths but applied by half degrees (#540), so it is written rounded to the
    nearest ``step`` words rather than left for the unit to truncate. Reads
    are not quantized: the register reports the word written.
    """

    factor: int
    step: int = 1

    def decode(self, raw: int) -> float | None:
        """Return the scaled value, or None for ``0xFFFF``."""
        return None if raw == NOT_EXPOSED else raw / self.factor

    def encode(self, value: Any) -> int:
        """Return the word for ``value``, rounded half up to the write resolution."""
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError(f"not a number: {value!r}")
        # One rounding, half up (not Python's half to even): 23.25 is written
        # 23.5 like 23.3, and 23.74 is 23.5.
        raw = math.floor(value * self.factor / self.step + 0.5) * self.step
        if not 0 <= raw < NOT_EXPOSED:
            raise ValueError(f"out of range: {value!r}")
        return raw


TENTHS = Scaled(10)
HALF_DEGREE = Scaled(10, step=5)
"""A temperature stored in tenths that the unit applies by half degrees (#540)."""
