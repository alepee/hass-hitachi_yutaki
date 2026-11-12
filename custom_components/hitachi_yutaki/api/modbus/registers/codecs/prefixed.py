"""Numeric codes exposed as translation keys (``alarm_code_42``)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .protocol import NOT_EXPOSED


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
