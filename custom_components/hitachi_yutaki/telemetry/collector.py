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
        """Return all buffered dicts and clear the buffer."""
        points = list(self._buffer)
        self._buffer.clear()
        return points

    def requeue(self, points: list[dict[str, Any]]) -> None:
        """Put previously flushed points back at the front of the buffer.

        Called when a send fails, so the batch is retried on the next flush
        instead of being lost. Two bounds apply: points older than
        MAX_POINT_AGE are dropped, and on overflow the newest points win.

        The explicit rebuild is deliberate. `deque.extendleft` on a bounded
        deque evicts from the right, i.e. the newest points — the opposite of
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
        self._buffer = deque(merged[-maxlen:] if maxlen else merged, maxlen=maxlen)
