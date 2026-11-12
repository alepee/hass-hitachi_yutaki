"""The contract every register codec implements."""

from __future__ import annotations

from typing import Any, Protocol

# The word an unsigned register returns when it carries no value. On a signed
# register the same word is -1, a valid reading (#533).
NOT_EXPOSED = 0xFFFF


class RegisterCodec(Protocol):
    """Two-way conversion between a register word and a value."""

    def decode(self, raw: int) -> Any:
        """Return the value of a raw 16-bit word, or None when it has none."""

    def encode(self, value: Any) -> int:
        """Return the raw 16-bit word for ``value``, raising ValueError/TypeError."""


def whole(value: Any) -> int:
    """Return ``value`` as an int, raising when it is not a whole number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"not a number: {value!r}")
    raw = int(value)
    if raw != value:
        raise ValueError(f"not a whole number: {value!r}")
    return raw
