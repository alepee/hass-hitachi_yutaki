"""Signed quantities, marked (*1): two's complement, ``0xFFFF`` is -1 (#533)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .protocol import whole


@dataclass(frozen=True)
class Signed:
    """A signed quantity in two's complement; ``0xFFFF`` is -1 (#533)."""

    def decode(self, raw: int) -> int:
        """Return the two's complement value of the word."""
        return raw - 0x10000 if raw > 0x7FFF else raw

    def encode(self, value: Any) -> int:
        """Return the two's complement word for a whole value."""
        raw = whole(value)
        if not -0x8000 <= raw <= 0x7FFF:
            raise ValueError(f"out of signed range: {value!r}")
        return raw & 0xFFFF


SIGNED = Signed()
