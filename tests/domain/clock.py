"""Controllable clock for deterministic service and adapter tests."""

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class FakeClock:
    """Advance elapsed time and civil time independently."""

    seconds: float = 10000.0
    wall: datetime = datetime(2026, 1, 1, 12, tzinfo=UTC)

    def monotonic(self) -> float:
        """Return controlled elapsed seconds."""
        return self.seconds

    def now(self) -> datetime:
        """Return controlled civil time."""
        return self.wall
