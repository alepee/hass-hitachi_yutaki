"""Unsigned quantities: ``0xFFFF`` carries no value."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .protocol import NOT_EXPOSED, whole


@dataclass(frozen=True)
class Unsigned:
    """An unsigned quantity; ``0xFFFF`` carries no value."""

    def decode(self, raw: int) -> int | None:
        """Return the word, or None for ``0xFFFF``."""
        return None if raw == NOT_EXPOSED else raw

    def encode(self, value: Any) -> int:
        """Return the word for a whole value in 0~65534."""
        raw = whole(value)
        if not 0 <= raw < NOT_EXPOSED:
            raise ValueError(f"out of unsigned range: {value!r}")
        return raw


UNSIGNED = Unsigned()
