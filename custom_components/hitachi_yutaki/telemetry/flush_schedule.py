"""When a config entry sends its buffered telemetry points, and how that stops.

A flush runs every cycle, plus one catch-up flush when a delivered batch left
points behind. Each flush runs as a background task of the entry.

Stopping is explicit, because Home Assistant cancels an entry's background
tasks only after ``async_unload_entry`` returns: the final unload flush would
otherwise run beside a periodic flush still in flight, two sends at once on an
endpoint that accepts one per minute, and the periodic flush, cancelled later,
would put its points back into a collector nobody flushes anymore.
:meth:`TelemetryFlushSchedule.async_stop` cancels the flushes in flight and
waits for them, so their points are back in the collector before the final
flush takes them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from ..const import DOMAIN

# How often buffered telemetry points are sent. Paired with the poll interval
# it also fixes how many points a cycle produces, hence the collect stride.
TELEMETRY_FLUSH_INTERVAL = timedelta(minutes=5)

# Delay before a catch-up flush, when a delivered batch left points behind.
# A flush is capped in bytes, so on the widest profiles one request carries
# fewer points than a 5s poll produces in a cycle and the buffer slowly
# saturates. One extra request per cycle doubles the drain rate. It sits past
# the endpoint's 60s rate-limit window and well before the next regular flush.
TELEMETRY_CATCHUP_DELAY = timedelta(seconds=65)


class TelemetryFlushSchedule:
    """The periodic and catch-up telemetry flushes of one config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        flush: Callable[[], Coroutine[object, object, bool]],
        backlog: Callable[[], int],
    ) -> None:
        """Wire the schedule; nothing runs until :meth:`start`.

        ``flush`` sends one batch and returns True when it was delivered;
        ``backlog`` returns how many points are still buffered.
        """
        self._hass = hass
        self._entry = entry
        self._flush = flush
        self._backlog = backlog
        self._cancel_interval: CALLBACK_TYPE | None = None
        self._cancel_catchup: CALLBACK_TYPE | None = None
        self._in_flight: set[asyncio.Task[object]] = set()
        self._stopped = False

    @callback
    def start(self) -> None:
        """Flush every cycle from now on."""
        self._cancel_interval = async_track_time_interval(
            self._hass, self._start_flush, TELEMETRY_FLUSH_INTERVAL
        )

    @callback
    def stop(self) -> None:
        """Start no more flushes; the ones in flight carry on. Idempotent."""
        self._stopped = True
        if self._cancel_interval is not None:
            self._cancel_interval()
            self._cancel_interval = None
        if self._cancel_catchup is not None:
            self._cancel_catchup()
            self._cancel_catchup = None

    async def async_stop(self) -> None:
        """Stop, then cancel the flushes in flight and wait until they are over.

        A cancelled flush puts its points back into the collector before it
        ends, so they are there for the final unload flush.
        """
        self.stop()
        tasks = list(self._in_flight)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks)

    @callback
    def _start_flush(self, _now: datetime) -> asyncio.Task[object]:
        return self._track(self._flush_cycle(), f"{DOMAIN} telemetry flush")

    @callback
    def _start_catchup(self, _now: datetime) -> asyncio.Task[object]:
        self._cancel_catchup = None
        return self._track(self._flush(), f"{DOMAIN} telemetry catch-up flush")

    def _track(
        self, job: Coroutine[object, object, object], name: str
    ) -> asyncio.Task[object]:
        """Run ``job`` as a background task of the entry, remembered until done."""
        task = self._entry.async_create_background_task(self._hass, job, name)
        self._in_flight.add(task)
        task.add_done_callback(self._in_flight.discard)
        return task

    async def _flush_cycle(self) -> None:
        delivered = await self._flush()
        # Only after a delivered batch: a backlog left by a failing send
        # waits for the next cycle rather than doubling the failed requests.
        if (
            delivered
            and self._backlog()
            and self._cancel_catchup is None
            and not self._stopped
        ):
            self._cancel_catchup = async_call_later(
                self._hass, TELEMETRY_CATCHUP_DELAY, self._start_catchup
            )
