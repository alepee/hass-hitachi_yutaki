"""Consent to send anonymous data, asked at the moment of sending.

The options flow writes the new options first and reloads the entry
afterwards. Every sender built at setup outlives that write until the reload
completes: the unload flush runs during it, and the instance's fleet pinger is
shared with the entry's siblings. A consent captured when a sender was built
would still say yes after the user said no, so senders are handed a consent
port instead and ask it before every emission, retries included.

This module is the single owner of the consent policy: which option means
what, and that telemetry ON implies the fleet ping.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from homeassistant.config_entries import ConfigEntry

from ..const import (
    CONF_FLEET_PING,
    CONF_TELEMETRY_LEVEL,
    DEFAULT_FLEET_PING,
    DEFAULT_TELEMETRY_LEVEL,
)
from .models import TelemetryLevel


class TelemetryConsent(Protocol):
    """Whether telemetry payloads may leave the instance right now."""

    def telemetry_allowed(self) -> bool:
        """Return True when the user currently consents to telemetry."""


class FleetPingConsent(Protocol):
    """Whether a unit may be listed in the fleet ping right now."""

    def fleet_ping_allowed(self) -> bool:
        """Return True when the user currently consents to the fleet ping."""


def is_telemetry_enabled(options: Mapping[str, Any]) -> bool:
    """Return whether these options consent to telemetry.

    Only an explicit ON consents. A missing or unknown level reads as OFF: a
    value this version does not understand is no consent.
    """
    level = options.get(CONF_TELEMETRY_LEVEL, DEFAULT_TELEMETRY_LEVEL)
    return level == TelemetryLevel.ON.value


def is_fleet_ping_enabled(options: Mapping[str, Any]) -> bool:
    """Return whether these options consent to the fleet ping.

    Telemetry ON implies the ping: telemetry already shares a superset of it,
    so opting out of the ping alone would make no sense. Otherwise the ping
    follows its own toggle, on by default.
    """
    if is_telemetry_enabled(options):
        return True
    return bool(options.get(CONF_FLEET_PING, DEFAULT_FLEET_PING))


class ConfigEntryConsent:
    """Consent read from a config entry's options each time it is asked.

    Holds the entry, never a copy of its options, so an options update is
    honoured from the moment it is written rather than from the next setup.
    """

    def __init__(self, entry: ConfigEntry) -> None:
        """Bind the consent to a config entry."""
        self._entry = entry

    def telemetry_allowed(self) -> bool:
        """Return True when the entry's current options consent to telemetry."""
        return is_telemetry_enabled(self._entry.options)

    def fleet_ping_allowed(self) -> bool:
        """Return True when the entry's current options consent to the ping."""
        return is_fleet_ping_enabled(self._entry.options)
