"""Anonymous daily fleet ping (#468).

One small payload per Home Assistant instance and per UTC day, listing the
Hitachi units of the instance and nothing that identifies it: no hash, no
coordinates (only a Köppen climate zone computed here), no metrics. Counting
the pings received on a day gives the number of active installations that day,
so no identifier is needed.

This is not telemetry. It has its own consent (opt-out, on by default), and
turning telemetry on implies it. Whether a config entry takes part is decided
by the caller, which registers a unit provider per participating entry,
together with that entry's consent: the pinger asks it again right before each
ping, because the user can withdraw it before the entry reloads.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime, timedelta
import gzip
import json
import logging
from pathlib import Path

import aiohttp

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, FLEET_PING_ENDPOINT, FLEET_PING_STATS_URL
from .consent import FleetPingConsent
from .models import FleetPing, FleetPingUnit

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}_fleet_ping"
DATA_KEY = f"{DOMAIN}_fleet_ping"
LEDGER_KEY = f"{DOMAIN}_fleet_ping_ledger"

# First attempt after HA start: late enough for every entry's first poll, so
# the day's ping lists all units rather than only the fastest gateway's.
INITIAL_DELAY = timedelta(minutes=10)
# Later attempts: a failed send, or a day boundary crossed while running.
CHECK_INTERVAL = timedelta(hours=1)
REQUEST_TIMEOUT = 10  # seconds

_KOPPEN_LOOKUP_PATH = Path(__file__).parent / "koppen_lookup.json"

UnitProvider = Callable[[], FleetPingUnit | None]


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


class FleetPingLedger:
    """Claim each UTC day's fleet ping for the whole Home Assistant instance.

    The single owner of "has today's ping been sent?". It outlives the pingers:
    a reload stops the pinger and starts a new one while the old one's POST
    may still be in flight, so the day is claimed here, in memory and
    synchronously, before the request leaves. A pinger that finds the day
    delivered or claimed does not send.

    A send whose outcome is unknown (cancelled mid-flight) counts as
    delivered: the ping is at most once a day, a missed day is preferable to
    a day counted twice.
    """

    def __init__(self, store: Store[dict[str, str]]) -> None:
        """Initialize the ledger. Call async_load before use."""
        self._store = store
        self._delivered: date | None = None
        self._claimed: date | None = None
        self._loaded = False

    @property
    def delivered(self) -> date | None:
        """Return the UTC day of the last delivered ping."""
        return self._delivered

    async def async_load(self) -> None:
        """Load the last delivered day from the store, once per HA run.

        Later calls keep the in-memory state, which may be ahead of the store.
        """
        if self._loaded:
            return
        self._loaded = True
        stored = await self._store.async_load() or {}
        if last_sent := stored.get("last_sent"):
            try:
                self._delivered = date.fromisoformat(last_sent)
            except ValueError:
                self._delivered = None

    @callback
    def claim(self, day: date) -> bool:
        """Reserve the day's ping. False when delivered or already in flight."""
        if day == self._delivered or self._claimed is not None:
            return False
        self._claimed = day
        return True

    @callback
    def settle(self, day: date, *, delivered: bool) -> None:
        """Close the claim; a delivered day is persisted, a failed one freed."""
        self._claimed = None
        if delivered:
            self._delivered = day
            # Not awaited: settle also runs while a cancelled send unwinds.
            self._store.async_delay_save(self._data_to_save, 0)

    def _data_to_save(self) -> dict[str, str]:
        """Return the persisted state."""
        assert self._delivered is not None
        return {"last_sent": self._delivered.isoformat()}


class FleetPinger:
    """Send the fleet ping at most once per UTC day for this HA instance."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        integration_version: str,
        ledger: FleetPingLedger,
        endpoint: str = FLEET_PING_ENDPOINT,
    ) -> None:
        """Initialize the pinger. Call async_start before use."""
        self._hass = hass
        self._session = session
        self._integration_version = integration_version
        self._ledger = ledger
        self._endpoint = endpoint
        self._providers: dict[str, tuple[UnitProvider, FleetPingConsent]] = {}
        self._climate_zone: str | None = None
        self._send_task: asyncio.Task[bool] | None = None
        self._unsubs: list[CALLBACK_TYPE] = []

    @property
    def last_sent(self) -> date | None:
        """Return the UTC day of the last delivered ping."""
        return self._ledger.delivered

    async def async_start(self) -> None:
        """Resolve the climate zone and arm the timers."""
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
        """Cancel the timers and a send in flight."""
        while self._unsubs:
            self._unsubs.pop()()
        if self._send_task is not None:
            self._send_task.cancel()
            self._send_task = None

    @callback
    def register(
        self, entry_id: str, provider: UnitProvider, consent: FleetPingConsent
    ) -> None:
        """Make a config entry's unit part of the ping, while it consents."""
        self._providers[entry_id] = (provider, consent)

    @callback
    def unregister(self, entry_id: str) -> bool:
        """Remove a config entry's unit. Return True when none is left."""
        self._providers.pop(entry_id, None)
        return not self._providers

    @callback
    def _async_scheduled(self, _now: datetime) -> None:
        """Timer callback: start a send owned by this pinger."""
        if self._send_task is not None and not self._send_task.done():
            return
        self._send_task = self._hass.async_create_background_task(
            self.async_maybe_send(), name=f"{DOMAIN} fleet ping"
        )

    async def async_maybe_send(self) -> bool:
        """Send today's ping unless it was already delivered or claimed.

        Return True when a ping was delivered by this call.
        """
        today = dt_util.utcnow().date()
        # Consent is asked here, not at registration: an entry whose user
        # just turned the ping off stays registered until it reloads.
        units = tuple(
            unit
            for provider, consent in self._providers.values()
            if consent.fleet_ping_allowed() and (unit := provider()) is not None
        )
        # No consenting unit has completed a poll yet: nothing to count.
        if not units:
            return False
        # Claimed before the first await, so no other pinger can send today.
        if not self._ledger.claim(today):
            return False

        ping = FleetPing(
            integration_version=self._integration_version,
            ha_version=HA_VERSION,
            climate_zone=self._climate_zone,
            units=units,
        )
        # Interrupted mid-flight, the ping may have reached the endpoint.
        delivered = True
        try:
            delivered = await self._async_post(ping)
        finally:
            self._ledger.settle(today, delivered=delivered)
        return delivered

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
    consent: FleetPingConsent,
) -> None:
    """Add an entry's unit to the instance's ping, starting the pinger if needed."""
    pinger: FleetPinger | None = hass.data.get(DATA_KEY)
    if pinger is None:
        ledger = _get_ledger(hass)
        pinger = FleetPinger(
            hass, async_get_clientsession(hass), integration_version, ledger
        )
        hass.data[DATA_KEY] = pinger
        await ledger.async_load()
        await pinger.async_start()
    pinger.register(entry_id, provider, consent)


@callback
def _get_ledger(hass: HomeAssistant) -> FleetPingLedger:
    """Return the instance's ledger, kept for the whole HA run.

    Unlike the pinger, it is never dropped: the pinger a reload starts must
    see the day the previous one claimed.
    """
    ledger: FleetPingLedger | None = hass.data.get(LEDGER_KEY)
    if ledger is None:
        ledger = FleetPingLedger(Store(hass, STORE_VERSION, STORE_KEY))
        hass.data[LEDGER_KEY] = ledger
    return ledger


@callback
def async_unregister_fleet_ping(hass: HomeAssistant, entry_id: str) -> None:
    """Remove an entry's unit, stopping the pinger once no entry takes part."""
    pinger: FleetPinger | None = hass.data.get(DATA_KEY)
    if pinger is None:
        return
    if pinger.unregister(entry_id):
        pinger.async_stop()
        hass.data.pop(DATA_KEY, None)
