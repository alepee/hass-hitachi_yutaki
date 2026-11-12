"""Closed lists of documented words (switches, modes, states, models)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


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


def choice(*raws: int) -> EnumCodec:
    """Return a codec for a register whose value is one of ``raws``, as is."""
    return EnumCodec({raw: raw for raw in raws})
