"""Telemetry collector — buffers coordinator data dicts for periodic send."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from .models import TelemetryLevel

_LOGGER = logging.getLogger(__name__)

# Default buffer size: 360 points = 30 minutes at 5s poll interval
DEFAULT_BUFFER_MAX_SIZE = 360

# Re-queued points older than this are dropped. Matches the buffer's natural
# window (360 points at a 5s poll interval) and bounds how long a broken
# installation can keep replaying failed sends (#395).
MAX_POINT_AGE = timedelta(minutes=30)

# Maximum points sent in one flush. Bounds the request body so a backlog can
# never outgrow the ingestion endpoint's payload limit, which the client
# cannot see. Above the ~60 points a 5-minute cycle produces at the default
# 5s poll, so a backlog still drains, and far enough under the limit to hold
# even on the widest profile (#395).
MAX_FLUSH_POINTS = 80

# Keys to exclude from telemetry (internal coordinator flags)
_EXCLUDED_KEYS = frozenset({"is_available"})


class TelemetryCollector:
    """Buffers coordinator data dicts for periodic telemetry send.

    Each call to collect() snapshots the data dict (minus excluded keys)
    and adds a UTC timestamp. The buffer is a circular deque — when full,
    oldest entries are dropped.
    """

    def __init__(
        self,
        level: TelemetryLevel,
        buffer_max_size: int = DEFAULT_BUFFER_MAX_SIZE,
    ) -> None:
        """Initialize the collector."""
        self._level = level
        self._buffer: deque[dict[str, Any]] = deque(maxlen=buffer_max_size)

    @property
    def level(self) -> TelemetryLevel:
        """Return the current telemetry level."""
        return self._level

    @property
    def buffer_size(self) -> int:
        """Return the current number of buffered points."""
        return len(self._buffer)

    def collect(self, data: dict[str, Any]) -> None:
        """Snapshot the data dict and add to the buffer.

        Skips collection when level is OFF or data is unavailable.
        """
        if self._level == TelemetryLevel.OFF:
            return

        if not data or not data.get("is_available"):
            return

        # Shallow copy, exclude internal keys, add timestamp
        point = {k: v for k, v in data.items() if k not in _EXCLUDED_KEYS}
        point["time"] = datetime.now(tz=UTC)

        self._buffer.append(point)

    def flush(self) -> list[dict[str, Any]]:
        """Return the oldest buffered dicts, at most MAX_FLUSH_POINTS of them.

        Points beyond the cap stay buffered and go out on the next flush, so a
        backlog drains over several cycles instead of growing into a single
        request the ingestion endpoint rejects as too large (#395). Nothing is
        dropped here: what is not returned is still buffered, in order.
        """
        if len(self._buffer) <= MAX_FLUSH_POINTS:
            points = list(self._buffer)
            self._buffer.clear()
            return points

        return [self._buffer.popleft() for _ in range(MAX_FLUSH_POINTS)]

    def requeue(self, points: list[dict[str, Any]]) -> None:
        """Put previously flushed points back at the front of the buffer.

        Called when a send fails, so the batch is retried on the next flush
        instead of being lost. Two bounds apply: points older than
        MAX_POINT_AGE are dropped, and on overflow the newest points win.

        The explicit rebuild is deliberate. `deque.extendleft` on a bounded
        deque evicts from the right, i.e. the newest points, the opposite of
        the intended policy.
        """
        if not points:
            return

        cutoff = datetime.now(tz=UTC) - MAX_POINT_AGE
        kept = [p for p in points if p.get("time") is not None and p["time"] >= cutoff]
        if not kept:
            return

        maxlen = self._buffer.maxlen
        merged = kept + list(self._buffer)
        # `is not None`, not truthiness: -0 == 0, so merged[-0:] would return
        # the whole list and silently make a maxlen=0 buffer unbounded.
        self._buffer = deque(
            merged[-maxlen:] if maxlen is not None else merged, maxlen=maxlen
        )
