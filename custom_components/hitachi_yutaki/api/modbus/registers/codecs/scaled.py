"""Quantities stored scaled (tenths, marked (*3)); ``0xFFFF`` carries no value."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .protocol import NOT_EXPOSED


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


TENTHS = Scaled(10)
