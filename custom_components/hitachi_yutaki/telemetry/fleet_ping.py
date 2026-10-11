"""Anonymous daily fleet ping (#468).

One small payload per Home Assistant instance and per UTC day, listing the
Hitachi units of the instance and nothing that identifies it: no hash, no
coordinates (only a Köppen climate zone computed here), no metrics. Counting
the pings received on a day gives the number of active installations that day,
so no identifier is needed.

This is not telemetry. It has its own consent (opt-out, on by default), and
turning telemetry on implies it. Whether a config entry takes part is decided
by the caller, which registers a unit provider per participating entry.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
import gzip
import json
import logging
from pathlib import Path
from typing import Any

import aiohttp

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_FLEET_PING,
    CONF_TELEMETRY_LEVEL,
    DEFAULT_FLEET_PING,
    DEFAULT_TELEMETRY_LEVEL,
    DOMAIN,
    FLEET_PING_ENDPOINT,
    FLEET_PING_STATS_URL,
)
from .models import FleetPing, FleetPingUnit, TelemetryLevel

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}_fleet_ping"
DATA_KEY = f"{DOMAIN}_fleet_ping"

# First attempt after HA start: late enough for every entry's first poll, so
# the day's ping lists all units rather than only the fastest gateway's.
INITIAL_DELAY = timedelta(minutes=10)
# Later attempts: a failed send, or a day boundary crossed while running.
CHECK_INTERVAL = timedelta(hours=1)
REQUEST_TIMEOUT = 10  # seconds

_KOPPEN_LOOKUP_PATH = Path(__file__).parent / "koppen_lookup.json"

UnitProvider = Callable[[], FleetPingUnit | None]


def is_fleet_ping_enabled(options: Mapping[str, Any]) -> bool:
    """Return whether a config entry takes part in the fleet ping.

    Telemetry ON implies the ping: telemetry already shares a superset of it,
    so opting out of the ping alone would make no sense. Otherwise the ping
    follows its own toggle, on by default.
    """
    telemetry = options.get(CONF_TELEMETRY_LEVEL, DEFAULT_TELEMETRY_LEVEL)
    if telemetry == TelemetryLevel.ON.value:
        return True
    return bool(options.get(CONF_FLEET_PING, DEFAULT_FLEET_PING))


def classify_climate_zone(
    lookup: dict[str, str], latitude: float | None, longitude: float | None
) -> str | None:
    """Return the Köppen-Geiger zone for a location, or None.

    The table is keyed on 1° cells, like the worker's copy it mirrors
    (Beck et al. 2018, via kgcpy). Only the zone ever leaves the instance.
    """
    if latitude is None or longitude is None:
        return None
    return lookup.get(f"{round(latitude)},{round(longitude)}")


def _load_koppen_lookup() -> dict[str, str]:
    """Load the Köppen table (blocking I/O, run in the executor)."""
    with _KOPPEN_LOOKUP_PATH.open(encoding="utf-8") as file:
        return json.load(file)


class FleetPinger:
    """Send the fleet ping at most once per UTC day for this HA instance."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        integration_version: str,
        endpoint: str = FLEET_PING_ENDPOINT,
    ) -> None:
        """Initialize the pinger. Call async_start before use."""
        self._hass = hass
        self._session = session
        self._integration_version = integration_version
        self._endpoint = endpoint
        self._store: Store[dict[str, str]] = Store(hass, STORE_VERSION, STORE_KEY)
        self._providers: dict[str, UnitProvider] = {}
        self._last_sent: date | None = None
        self._climate_zone: str | None = None
        self._lock = asyncio.Lock()
        self._unsubs: list[CALLBACK_TYPE] = []

    @property
    def last_sent(self) -> date | None:
        """Return the UTC day of the last delivered ping."""
        return self._last_sent

    async def async_start(self) -> None:
        """Load the persisted state, resolve the climate zone, arm the timers."""
        stored = await self._store.async_load() or {}
        if last_sent := stored.get("last_sent"):
            try:
                self._last_sent = date.fromisoformat(last_sent)
            except ValueError:
                self._last_sent = None

        lookup = await self._hass.async_add_executor_job(_load_koppen_lookup)
        self._climate_zone = classify_climate_zone(
            lookup, self._hass.config.latitude, self._hass.config.longitude
        )

        self._unsubs.append(
            async_call_later(self._hass, INITIAL_DELAY, self._async_scheduled)
        )
        self._unsubs.append(
            async_track_time_interval(self._hass, self._async_scheduled, CHECK_INTERVAL)
        )
        _LOGGER.info(
            "Anonymous fleet ping enabled: once a day, the integration sends its "
            "version, the Home Assistant version, the climate zone and the "
            "heat pump models, with no identifier and no location. Public "
            "stats: %s. It can be turned off in the integration options",
            FLEET_PING_STATS_URL,
        )

    @callback
    def async_stop(self) -> None:
        """Cancel the timers."""
        while self._unsubs:
            self._unsubs.pop()()

    @callback
    def register(self, entry_id: str, provider: UnitProvider) -> None:
        """Make a config entry's unit part of the ping."""
        self._providers[entry_id] = provider

    @callback
    def unregister(self, entry_id: str) -> bool:
        """Remove a config entry's unit. Return True when none is left."""
        self._providers.pop(entry_id, None)
        return not self._providers

    async def _async_scheduled(self, _now: datetime) -> None:
        """Timer callback."""
        await self.async_maybe_send()

    async def async_maybe_send(self) -> bool:
        """Send today's ping unless it was already delivered.

        Return True when a ping was delivered by this call.
        """
        if self._lock.locked():
            return False
        async with self._lock:
            today = dt_util.utcnow().date()
            if self._last_sent == today:
                return False

            units = tuple(
                unit
                for provider in self._providers.values()
                if (unit := provider()) is not None
            )
            # No unit has completed a poll yet: nothing worth counting.
            if not units:
                return False

            ping = FleetPing(
                integration_version=self._integration_version,
                ha_version=HA_VERSION,
                climate_zone=self._climate_zone,
                units=units,
            )
            if not await self._async_post(ping):
                return False

            self._last_sent = today
            await self._store.async_save({"last_sent": today.isoformat()})
            return True

    async def _async_post(self, ping: FleetPing) -> bool:
        """POST the ping. Single attempt: the hourly check is the retry."""
        body = gzip.compress(json.dumps(ping.to_dict()).encode())
        # No X-Instance-Hash header, unlike telemetry: the ping has no identity.
        headers = {"Content-Type": "application/json", "Content-Encoding": "gzip"}
        try:
            async with self._session.post(
                self._endpoint,
                data=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if 200 <= resp.status < 300:
                    return True
                _LOGGER.debug("Fleet ping rejected (HTTP %s)", resp.status)
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug("Fleet ping failed: %s", err)
        return False


async def async_register_fleet_ping(
    hass: HomeAssistant,
    entry_id: str,
    integration_version: str,
    provider: UnitProvider,
) -> None:
    """Add an entry's unit to the instance's ping, starting the pinger if needed."""
    pinger: FleetPinger | None = hass.data.get(DATA_KEY)
    if pinger is None:
        pinger = FleetPinger(hass, async_get_clientsession(hass), integration_version)
        hass.data[DATA_KEY] = pinger
        await pinger.async_start()
    pinger.register(entry_id, provider)


@callback
def async_unregister_fleet_ping(hass: HomeAssistant, entry_id: str) -> None:
    """Remove an entry's unit, stopping the pinger once no entry takes part."""
    pinger: FleetPinger | None = hass.data.get(DATA_KEY)
    if pinger is None:
        return
    if pinger.unregister(entry_id):
        pinger.async_stop()
        hass.data.pop(DATA_KEY, None)
