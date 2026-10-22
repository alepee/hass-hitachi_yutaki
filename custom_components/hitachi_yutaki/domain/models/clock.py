"""Deterministic time resolution for live services and historical replay."""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from ..ports.clock import Clock


def validate_timestamp_awareness(timestamps: Iterable[datetime]) -> None:
    """Reject mixed naive/aware timelines before mutating history buffers."""
    awareness = {timestamp.utcoffset() is not None for timestamp in timestamps}
    if len(awareness) > 1:
        raise ValueError("History timestamps must share timezone awareness")


def civil_time(clock: Clock | None, timestamp: datetime | None) -> datetime:
    """Resolve explicit replay time or an injected clock, never the system clock."""
    if timestamp is not None:
        return timestamp
    if clock is None:
        raise ValueError("An injected clock or explicit timestamp is required")
    return clock.now()


def elapsed_time(clock: Clock | None, timestamp: datetime | None) -> float:
    """Use replay timestamps consistently, or live monotonic seconds."""
    if timestamp is not None:
        # Treat naive replay timestamps as an unambiguous synthetic UTC timeline.
        return (
            timestamp.replace(tzinfo=UTC).timestamp()
            if timestamp.tzinfo is None
            else timestamp.timestamp()
        )
    if clock is None:
        raise ValueError("An injected clock or explicit timestamp is required")
    return clock.monotonic()


class Timeline:
    """Anchor live durations once, preserving explicit historical timestamps.

    Live timestamps advance by monotonic time after the initial civil-time
    anchor. Clock corrections and DST cannot invent elapsed energy or cycles.
    """

    def __init__(self, clock: Clock | None) -> None:
        """Accept a clock, or require timestamps on every read."""
        self._clock = clock
        self._anchor: datetime | None = None
        self._origin = 0.0

    def at(self, timestamp: datetime | None = None) -> datetime:
        """Return an elapsed-time timestamp, normalized to UTC when aware."""
        if timestamp is not None:
            return timestamp.astimezone(UTC) if timestamp.tzinfo else timestamp
        current = elapsed_time(self._clock, None)
        if self._anchor is None:
            now = civil_time(self._clock, None)
            self._anchor = now.astimezone(UTC) if now.tzinfo else now
            self._origin = current
        return self._anchor + timedelta(seconds=current - self._origin)
