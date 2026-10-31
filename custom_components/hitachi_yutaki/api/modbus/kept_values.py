"""Values a hardware reboot clears, and what to write back (#511).

Pure bookkeeping, no I/O: the Modbus client feeds it what it read and wrote,
and executes the writes it plans. Everything it knows about a register comes
from its ``Keep`` declaration, so it never interprets a value.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping
import logging
from typing import Any

from .registers import Keep, RegisterDefinition, validate_kept_registers

_LOGGER = logging.getLogger(__name__)

# Write-backs of a lost value before giving up on it.
MAX_RESTORE_ATTEMPTS = 3


def is_lost(keep: Keep, value: Any) -> bool:
    """Return True for a reading that a reboot leaves behind."""
    if value == 0:
        return True
    if keep.valid_range is None:
        return False
    low, high = keep.valid_range
    return not low <= value <= high


class KeptValues:
    """References of the kept values, the lost ones, and the write-back plan.

    A value is restored to its reference (the last value written, or the last
    reading that was not lost), or copied from its ``seed_from`` source. It
    waits until everything that must go before it reads right and is
    confirmed: the values that depend on it (``while_on``) and the values
    seeded from it (``seed_from``). A value whose ``while_on`` is off is left
    alone, the unit ignores it.
    """

    def __init__(
        self, registers: Mapping[str, RegisterDefinition], writable_keys: set[str]
    ) -> None:
        """Index the ``Keep`` declarations of a register map, validating them."""
        validate_kept_registers(registers, writable_keys)
        self._registers = registers
        self._keeps = {k: d.keep for k, d in registers.items() if d.keep is not None}
        # key -> kept values that must read right before ``key`` is written.
        self._before = {
            key: [
                other
                for other, keep in self._keeps.items()
                if key in (keep.while_on, keep.seed_from)
            ]
            for key in self._keeps
        }
        self._references: dict[str, Any] = {}
        self._lost: dict[str, Any] = {}
        self._attempts: dict[str, int] = {}
        self._failed: set[str] = set()
        self._unrestorable: set[str] = set()
        self._was_unrestorable: set[str] = set()
        self._listener: Callable[[], None] | None = None

    # --- References -------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return the references, to persist."""
        return dict(self._references)

    def load(self, values: Mapping[str, Any]) -> None:
        """Load persisted references, skipping anything not trustworthy."""
        for key, value in values.items():
            keep = self._keeps.get(key)
            if (
                keep is None
                or keep.seed_from is not None
                or isinstance(value, bool)
                or not isinstance(value, int | float)
                or (self._registers[key].deserializer is None and value != int(value))
            ):
                continue
            if keep.valid_range is None or (
                keep.valid_range[0] <= value <= keep.valid_range[1]
            ):
                self._references[key] = value

    def listen(self, listener: Callable[[], None]) -> None:
        """Call ``listener`` whenever a reference changes."""
        self._listener = listener

    def written(self, key: str, value: Any, *, by_restore: bool) -> None:
        """Record a successful write; a command from Home Assistant settles a restore."""
        keep = self._keeps.get(key)
        if keep is None:
            return
        if keep.seed_from is None:
            self._remember(key, value)
        if not by_restore:
            self._settle(key)

    def wanted(self, key: str, value: Any) -> bool:
        """Return False when Home Assistant changed a reference after the plan."""
        return self._keeps[key].seed_from is not None or (
            self._references.get(key) == value
        )

    # --- Reads and plan ---------------------------------------------------

    def discard_lost(self) -> None:
        """Forget the lost values queued by an earlier read."""
        self._lost = {}

    def track(self, fresh: Iterable[str], data: Mapping[str, Any]) -> None:
        """Compare the kept values just read with their references."""
        self._was_unrestorable, self._unrestorable = self._unrestorable, set()
        self._lost = {}
        for key in fresh:
            if key in self._keeps and key in data:
                if is_lost(self._keeps[key], data[key]):
                    self._read_lost(key, data)
                else:
                    self._read_right(key, data[key])

    def _read_right(self, key: str, value: Any) -> None:
        """Settle a value read right and make the reading its reference."""
        self._settle(key)
        if self._keeps[key].seed_from is None:
            self._remember(key, value)

    def _read_lost(self, key: str, data: Mapping[str, Any]) -> None:
        """Queue a lost reading, or report it when nothing can bring it back."""
        keep, value = self._keeps[key], data[key]
        if keep.seed_from is not None:
            self._lost[key] = None
        elif key in self._references:
            if self._references[key] != value:
                self._lost[key] = self._references[key]
        elif keep.while_on is not None and data.get(keep.while_on):
            self._mark_unrestorable(
                key, "%s reads %s with no known value to write back", key, value
            )

    def plan(
        self, data: Mapping[str, Any], pending: Collection[str]
    ) -> list[tuple[str, Any]]:
        """Return the write-backs to perform now, consuming the lost values."""
        lost, self._lost = self._lost, {}
        writes = []
        for key in lost:
            value = self._plan_one(key, lost, data, pending)
            if value is not None:
                writes.append((key, value))
        return writes

    def _plan_one(
        self,
        key: str,
        lost: Mapping[str, Any],
        data: Mapping[str, Any],
        pending: Collection[str],
    ) -> Any:
        """Return the value to write ``key`` back with now, or None to wait."""
        gate = self._keeps[key].while_on
        if gate is not None and not (gate in lost or data.get(gate)):
            self._settle(key)
            return None
        value = self._value_for(key, lost, data)
        if key in self._failed or value is None:
            return None
        blockers = [k for k in self._before[key] if not self._settled(k, data, pending)]
        if any(k not in data for k in blockers):
            return None
        if blockers:
            if not any(self._restorable(k, lost, data, pending) for k in blockers):
                self._mark_unrestorable(
                    key, "%s cannot be written back before %s", key, ", ".join(blockers)
                )
            return None
        return value if self._take_attempt(key, data) else None

    def _value_for(
        self, key: str, lost: Mapping[str, Any], data: Mapping[str, Any]
    ) -> Any:
        """Return the reference of ``key``, or what it is seeded with."""
        source = self._keeps[key].seed_from
        if source is None:
            return lost[key]
        if source in lost:
            return lost[source]
        if source in data and not is_lost(self._keeps[source], data[source]):
            return data[source]
        return None

    def _settled(
        self, key: str, data: Mapping[str, Any], pending: Collection[str]
    ) -> bool:
        """Return True for a value read right and not awaiting confirmation."""
        return (
            key in data
            and key not in pending
            and not is_lost(self._keeps[key], data[key])
        )

    def _restorable(
        self,
        key: str,
        lost: Mapping[str, Any],
        data: Mapping[str, Any],
        pending: Collection[str],
    ) -> bool:
        """Return True when a write-back of ``key`` is under way or possible."""
        if key in pending:
            return True
        return key in lost and self._value_for(key, lost, data) is not None

    # --- Attempts and reporting -------------------------------------------

    @property
    def failed(self) -> bool:
        """Return True while a lost value could not be written back."""
        return bool(self._failed or self._unrestorable)

    def retry(self) -> None:
        """Give every value that could not be written back a fresh set of attempts."""
        self._attempts.clear()
        self._failed.clear()
        self._unrestorable.clear()
        self._was_unrestorable.clear()

    def _take_attempt(self, key: str, data: Mapping[str, Any]) -> bool:
        """Count one more write-back, or give up past the limit."""
        attempts = self._attempts.get(key, 0)
        if attempts >= MAX_RESTORE_ATTEMPTS:
            _LOGGER.warning(
                "%s still reads %s after %d write-backs, giving up",
                key,
                data.get(key),
                attempts,
            )
            self._failed.add(key)
            return False
        self._attempts[key] = attempts + 1
        _LOGGER.warning("%s reads %s, likely after a reboot", key, data.get(key))
        return True

    def _mark_unrestorable(self, key: str, message: str, *args: Any) -> None:
        """Report a lost value that cannot be written back, logged once per spell."""
        if key not in self._was_unrestorable:
            _LOGGER.warning(message, *args)
        self._unrestorable.add(key)

    def _settle(self, key: str) -> None:
        """Forget the attempts and failure of a value that reads right again."""
        self._attempts.pop(key, None)
        self._failed.discard(key)

    def _remember(self, key: str, value: Any) -> None:
        """Record the reference a kept value is written back to."""
        if self._references.get(key) != value:
            self._references[key] = value
            if self._listener is not None:
                self._listener()
