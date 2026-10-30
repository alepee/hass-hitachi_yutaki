"""Keep a circuit's room regulation across a power cycle (#511).

A controller board reset zeroes the room target while the External room
sensor flag stays on; a gateway reset lowers the flag and keeps the target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Documented range of the "Thermostat Setting Temperature" register.
TARGET_MIN = 5.0
TARGET_MAX = 35.0

MAX_RESTORE_ATTEMPTS = 3

# Longer than the gateway client's pending-write shadow (30 s): a restore is
# confirmed by a STATUS read, never by the echo of its own write.
CONFIRM_AFTER_S = 60.0


def is_valid_target(target: float | None) -> bool:
    """Return True for a target inside the register's documented range."""
    return target is not None and TARGET_MIN <= target <= TARGET_MAX


def _mapping(value: Any) -> dict[Any, Any]:
    """Return a stored section as a dict, anything else as empty."""
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class RoomRestore:
    """What to write back for a circuit: the target first, then the flag."""

    target: float | None = None
    enable: bool = False


@dataclass
class _Restore:
    attempts: int = 0
    last_at: float | None = None
    failed: bool = False

    def settled(self, now: float) -> bool:
        """Return True once a reading cannot be the echo of the last write."""
        return self.last_at is None or now - self.last_at >= CONFIRM_AFTER_S

    def attempt(self, now: float) -> bool:
        """Count one more write, or give up past the attempt limit."""
        if self.failed:
            return False
        if self.attempts >= MAX_RESTORE_ATTEMPTS:
            self.failed = True
            return False
        self.attempts += 1
        self.last_at = now
        return True


class RoomTargetKeeper:
    """Remember each circuit's room target and flag, and say when to restore them.

    Pure rule: the caller reads the registers, writes the returned
    ``RoomRestore`` and persists ``serialize()`` when ``take_dirty()`` reports
    a change.
    """

    def __init__(self, stored: dict[Any, Any] | None = None) -> None:
        """Initialize from a persisted snapshot (see ``serialize``)."""
        stored = stored or {}
        self._targets: dict[int, float] = {}
        for key, value in _mapping(stored.get("targets")).items():
            try:
                circuit_id, target = int(key), float(value)
            except (TypeError, ValueError):
                continue
            if is_valid_target(target):
                self._targets[circuit_id] = target
        self._enabled: dict[int, bool] = {}
        for key, value in _mapping(stored.get("enabled")).items():
            try:
                self._enabled[int(key)] = bool(value)
            except (TypeError, ValueError):
                continue
        self._target_state: dict[int, _Restore] = {}
        self._flag_state: dict[int, _Restore] = {}
        self._dirty = False

    def stored_target(self, circuit_id: int) -> float | None:
        """Return the remembered target of a circuit, if any."""
        return self._targets.get(circuit_id)

    def stored_enabled(self, circuit_id: int) -> bool:
        """Return whether the circuit's flag was last seen on."""
        return self._enabled.get(circuit_id, False)

    def observe(
        self,
        circuit_id: int,
        enabled: bool | None,
        target: float | None,
        now: float,
        *,
        keep_enabled: bool = False,
        after_gap: bool = False,
    ) -> RoomRestore:
        """Record one poll's reading and return what to write back.

        ``enabled`` is the External room sensor flag, ``now`` a monotonic time
        in seconds. ``keep_enabled`` opts the circuit into the flag restore and
        ``after_gap`` marks the first good poll after a failure, when a gateway
        reset shows up. An unread flag or target decides nothing.
        """
        if enabled is None or target is None:
            return RoomRestore()
        raise_flag = self._observe_flag(
            circuit_id, enabled, now, keep_enabled, after_gap
        )
        write = self._observe_target(circuit_id, enabled or raise_flag, target, now)
        enable = False
        if raise_flag and (write is not None or is_valid_target(target)):
            # Never raise the flag on a target of 0: the unit would then
            # regulate on a room value that nothing feeds.
            enable = self._flag_state[circuit_id].attempt(now)
        return RoomRestore(target=write, enable=enable)

    def _observe_target(
        self, circuit_id: int, enabled: bool, target: float, now: float
    ) -> float | None:
        state = self._target_state.setdefault(circuit_id, _Restore())
        if is_valid_target(target):
            if state.settled(now):
                self._target_state[circuit_id] = _Restore()
            if self._targets.get(circuit_id) != target:
                self._targets[circuit_id] = target
                self._dirty = True
            return None
        if not enabled:
            # The unit does not regulate on the room registers: nothing to do.
            self._target_state[circuit_id] = _Restore()
            return None
        stored = self._targets.get(circuit_id)
        if stored is None or not state.attempt(now):
            return None
        return stored

    def _observe_flag(
        self, circuit_id: int, enabled: bool, now: float, keep: bool, after_gap: bool
    ) -> bool:
        """Record the flag and return True when it should be raised again."""
        if not keep:
            self._flag_state.pop(circuit_id, None)
            return False
        state = self._flag_state.setdefault(circuit_id, _Restore())
        if enabled:
            if state.settled(now):
                self._flag_state[circuit_id] = _Restore()
            if not self._enabled.get(circuit_id):
                self._enabled[circuit_id] = True
                self._dirty = True
            return False
        if not self._enabled.get(circuit_id) or state.failed:
            return False
        if state.last_at is None:
            if not after_gap:
                # Lowered while the gateway stayed reachable: Home Assistant did it.
                self._enabled[circuit_id] = False
                self._dirty = True
                return False
            # Wanted from now on, even if the target has to come back first.
            state.last_at = now
        return True

    def failed_circuits(self) -> list[int]:
        """Return the circuits whose target could not be restored."""
        return sorted(cid for cid, s in self._target_state.items() if s.failed)

    def failed_flag_circuits(self) -> list[int]:
        """Return the circuits whose flag could not be raised again."""
        return sorted(cid for cid, s in self._flag_state.items() if s.failed)

    def take_dirty(self) -> bool:
        """Return True once after the remembered values changed."""
        dirty, self._dirty = self._dirty, False
        return dirty

    def serialize(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the remembered values."""
        return {
            "targets": {str(cid): t for cid, t in sorted(self._targets.items())},
            "enabled": {str(cid): e for cid, e in sorted(self._enabled.items())},
        }
