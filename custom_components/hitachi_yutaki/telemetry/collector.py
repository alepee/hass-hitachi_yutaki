"""Telemetry collector — buffers coordinator data dicts for periodic send."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime, timedelta
import json
import logging
from math import ceil
from typing import Any

from .models import TelemetryLevel

_LOGGER = logging.getLogger(__name__)

# Default buffer size: 360 points = 30 minutes at 5s poll interval. Prefer
# compute_buffer_max_size, which expresses the same 30-minute window at any
# poll cadence; this constant is the value it yields for the default poll.
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

# Serialized budget for one request body, well under the endpoint's 256 KB
# decompressed limit. A point count cannot bound bytes on its own: a point
# carries one field per register plus the derived metrics, so the widest
# profiles reach roughly 3 KB per point against roughly 1.1 KB on the
# narrowest, and 80 of them measure about 233 KB. The margin the point cap
# alone leaves is therefore a property of the profile, not of the cap (#395).
MAX_FLUSH_BYTES = 180 * 1024

# One warning per this many silently evicted points, so a saturated buffer is
# visible in the log without flooding it.
_OVERFLOW_LOG_EVERY = 100

# Keys to exclude from telemetry (internal coordinator flags)
_EXCLUDED_KEYS = frozenset({"is_available"})


def compute_buffer_max_size(scan_interval: timedelta, stride: int = 1) -> int:
    """Return how many points hold MAX_POINT_AGE at this collection cadence.

    The buffer window and the re-queue age cutoff must say the same thing.
    A fixed point count does not: 360 points is 30 minutes at the default 5s
    poll but six hours at a 60s one, while requeue discards anything older
    than MAX_POINT_AGE either way.
    """
    interval = scan_interval.total_seconds() * max(1, stride)
    if interval <= 0:
        return DEFAULT_BUFFER_MAX_SIZE
    return max(1, ceil(MAX_POINT_AGE.total_seconds() / interval))


def compute_collect_stride(scan_interval: timedelta, flush_interval: timedelta) -> int:
    """Return how many polls make up one collected telemetry point.

    A flush sends at most MAX_FLUSH_POINTS, while polling cadence is a user
    setting with no lower bound. Below roughly a 3.75s scan interval the poll
    produces more points per cycle than a flush can drain, the buffer
    saturates and the deque evicts points silently and forever (#395).

    Decimating collection at the source keeps production at or under the drain
    rate, so the loss becomes an explicit, evenly spread resolution choice
    instead of an invisible one. The stride is 1 whenever a cycle already fits
    under the cap, which covers the default 5s poll and anything slower, so
    normal installations collect every poll exactly as before.
    """
    scan = scan_interval.total_seconds()
    flush = flush_interval.total_seconds()
    if scan <= 0 or flush <= 0:
        return 1
    return max(1, ceil(flush / scan / MAX_FLUSH_POINTS))


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
        collect_stride: int = 1,
    ) -> None:
        """Initialize the collector.

        `collect_stride` keeps one poll out of N, see compute_collect_stride.
        """
        self._level = level
        self._buffer: deque[dict[str, Any]] = deque(maxlen=buffer_max_size)
        self._stride = max(1, collect_stride)
        self._polls = 0
        self._points_dropped = 0

    @property
    def level(self) -> TelemetryLevel:
        """Return the current telemetry level."""
        return self._level

    @property
    def buffer_size(self) -> int:
        """Return the current number of buffered points."""
        return len(self._buffer)

    @property
    def collect_stride(self) -> int:
        """Return how many polls make up one collected point."""
        return self._stride

    @property
    def points_dropped(self) -> int:
        """Return how many points a full buffer has evicted since startup."""
        return self._points_dropped

    def collect(self, data: dict[str, Any]) -> None:
        """Snapshot the data dict and add to the buffer.

        Skips collection when level is OFF or data is unavailable.
        """
        if self._level == TelemetryLevel.OFF:
            return

        if not data or not data.get("is_available"):
            return

        # Count only polls that carry usable data, so an unavailable gateway
        # does not shift which polls the stride keeps.
        self._polls += 1
        if self._polls % self._stride:
            return

        # Shallow copy, exclude internal keys, add timestamp
        point = {k: v for k, v in data.items() if k not in _EXCLUDED_KEYS}
        point["time"] = datetime.now(tz=UTC)

        maxlen = self._buffer.maxlen
        if maxlen is not None and len(self._buffer) == maxlen:
            # deque.append evicts the oldest point without a word. A backlog
            # this deep means sends are failing, so say so (#395).
            self._note_dropped(1)

        self._buffer.append(point)

    def flush(self) -> list[dict[str, Any]]:
        """Return the oldest buffered dicts, bounded by size and by count.

        Points beyond the bound stay buffered and go out on the next flush, so
        a backlog drains over several cycles instead of growing into a single
        request the ingestion endpoint rejects as too large (#395). Nothing is
        dropped here: what is not returned is still buffered, in order.

        The binding bound is MAX_FLUSH_BYTES, measured on the oldest point, so
        a wide profile sends fewer points rather than an oversized body.
        MAX_FLUSH_POINTS stays as an upper bound for narrow profiles, whose
        points are small enough that the byte budget would allow far more than
        a cycle ever produces.
        """
        if not self._buffer:
            return []

        limit = min(MAX_FLUSH_POINTS, self._points_within_budget())
        if len(self._buffer) <= limit:
            points = list(self._buffer)
            self._buffer.clear()
            return points

        return [self._buffer.popleft() for _ in range(limit)]

    def _points_within_budget(self) -> int:
        """Return how many points of the current width fit in MAX_FLUSH_BYTES.

        The oldest point stands for the batch: every point of one installation
        carries the same register keys, so their sizes differ only by the
        width of the values. Measured before anonymization, which only rounds
        values and can therefore shorten them, never lengthen them.
        """
        try:
            size = len(json.dumps(self._buffer[0], default=str).encode())
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return MAX_FLUSH_POINTS
        if size <= 0:
            return MAX_FLUSH_POINTS
        return max(1, MAX_FLUSH_BYTES // size)

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
        retained = merged[-maxlen:] if maxlen is not None else merged
        self._note_dropped(len(merged) - len(retained))
        self._buffer = deque(retained, maxlen=maxlen)

    def _note_dropped(self, count: int) -> None:
        """Account for evicted points and warn periodically."""
        if count <= 0:
            return

        before = self._points_dropped
        self._points_dropped += count
        if before == 0 or before // _OVERFLOW_LOG_EVERY != (
            self._points_dropped // _OVERFLOW_LOG_EVERY
        ):
            _LOGGER.warning(
                "Telemetry buffer full, %d point(s) dropped so far",
                self._points_dropped,
            )
