"""Telemetry collector — buffers coordinator data dicts for periodic send."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
import logging
from typing import Any

from .models import TelemetryLevel

_LOGGER = logging.getLogger(__name__)

# Default buffer size: 360 points = 30 minutes at 5s poll interval
DEFAULT_BUFFER_MAX_SIZE = 360

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
