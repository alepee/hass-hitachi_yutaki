"""Time dependency: elapsed durations and local civil time are distinct."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Provide monotonic seconds and timezone-aware local civil time."""

    def monotonic(self) -> float:
        """Return elapsed seconds from an arbitrary, stable origin."""
        ...

    def now(self) -> datetime:
        """Return civil time in the installation's timezone."""
        ...
