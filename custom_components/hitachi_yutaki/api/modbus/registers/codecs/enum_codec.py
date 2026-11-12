"""Closed lists of documented words: the register map declares the values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, eq=False)
class EnumCodec:
    """A closed list of documented words, each mapped to a value.

    The values are the gateway's, declared by its register map: the codec
    only applies them. A word outside ``reads`` decodes to ``unknown``;
    encoding a value outside ``writes`` raises, so a bad command is refused
    instead of written.

    ``writes`` defaults to the inverse of ``reads``. Give it when the register
    writes a subset, or when several words read as one value (e.g. a STATUS
    bit field read back from a plain CONTROL value). Every write must read
    back as the value written, checked at construction.
    """

    reads: Mapping[int, Any]
    writes: Mapping[Any, int] | None = None
    unknown: Any = None
    _writes: Mapping[Any, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Index the words to write, and check each one reads back."""
        writes = self.writes
        if writes is None:
            writes = {value: raw for raw, value in self.reads.items()}
            if len(writes) != len(self.reads):
                raise ValueError("several words read as one value: give writes")
        for value, raw in writes.items():
            if raw not in self.reads or self.reads[raw] != value:
                raise ValueError(
                    f"{value!r} is written as {raw}, which reads back otherwise"
                )
        object.__setattr__(self, "_writes", dict(writes))

    def decode(self, raw: int) -> Any:
        """Return the value of a documented word, else ``unknown``."""
        return self.reads.get(raw, self.unknown)

    def encode(self, value: Any) -> int:
        """Return the word of a writable value."""
        if isinstance(value, bool):
            value = int(value)
        try:
            return self._writes[value]
        except (KeyError, TypeError):
            raise ValueError(f"not a writable value: {value!r}") from None


def choice(*raws: int) -> EnumCodec:
    """Return a codec for a register whose value is one of ``raws``, as is."""
    return EnumCodec({raw: raw for raw in raws})
