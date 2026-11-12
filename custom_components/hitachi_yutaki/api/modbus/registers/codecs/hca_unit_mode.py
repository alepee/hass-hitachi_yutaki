"""HC-A(16/64)MB unit mode: STATUS bit field on read, CONTROL value on write."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HcaUnitMode:
    """Unit mode: read as STATUS bits (offset 101), written as CONTROL (51).

    STATUS encodes B0 = 0 cool / 1 heat and B1 = 0 normal / 1 auto, decoded
    to the ATW-MBS-02 values (0 cool, 1 heat, 2 auto). CONTROL only takes
    0 cool / 1 heat: auto cannot be commanded on this gateway. A word outside
    the two bits (e.g. 0xFFFF, which read as auto before #534) is no mode.
    """

    def decode(self, raw: int) -> int | None:
        """Return 0 cool, 1 heat or 2 auto, or None for an undocumented word."""
        if raw > 0b11:
            return None
        return 2 if raw & 0b10 else raw & 0b01

    def encode(self, value: Any) -> int:
        """Return the CONTROL word for cool (0) or heat (1)."""
        if isinstance(value, bool) or value not in (0, 1):
            raise ValueError(f"not a commandable unit mode: {value!r}")
        return int(value)


HCA_UNIT_MODE = HcaUnitMode()
