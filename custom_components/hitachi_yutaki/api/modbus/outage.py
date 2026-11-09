"""How long the gateway has been not ready, and when to say so (#356).

Pure bookkeeping, no I/O and no clock: the Modbus client passes the monotonic
time of each poll and logs what this object tells it to.
"""

from __future__ import annotations

from enum import Enum

# Interval between two "still not ready" reminders, in seconds.
REMINDER_INTERVAL = 300.0


class NotReadyWarning(Enum):
    """Which warning a not-ready poll calls for."""

    FIRST = "first"
    REMINDER = "reminder"


class GatewayOutage:
    """Track a gateway outage and throttle its warnings.

    The first not-ready poll warns, later ones stay silent until a reminder
    is due every :data:`REMINDER_INTERVAL`, and the first ready poll after an
    outage reports how long it lasted.
    """

    def __init__(self, reminder_interval: float = REMINDER_INTERVAL) -> None:
        """Start with no outage in progress."""
        self._reminder_interval = reminder_interval
        self.since: float | None = None
        self.last_warning: float = 0.0

    def duration(self, now: float) -> float:
        """Return how long the current outage has lasted, 0 without one."""
        if self.since is None:
            return 0.0
        return max(0.0, now - self.since)

    def not_ready(self, now: float) -> NotReadyWarning | None:
        """Record a not-ready poll; return the warning it calls for, if any."""
        if self.since is None:
            self.since = now
            self.last_warning = now
            return NotReadyWarning.FIRST
        if now - self.last_warning >= self._reminder_interval:
            self.last_warning = now
            return NotReadyWarning.REMINDER
        return None

    def ready(self, now: float) -> float | None:
        """Record a ready poll; return the outage duration if one just ended."""
        if self.since is None:
            return None
        elapsed = self.duration(now)
        self.since = None
        self.last_warning = 0.0
        return elapsed
