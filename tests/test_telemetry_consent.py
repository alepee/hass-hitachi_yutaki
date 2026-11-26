"""Consent is read at the moment of sending, not at configuration time.

Turning telemetry or the fleet ping off in the options flow writes the new
options first and reloads the entry afterwards. Every sender built at setup
outlives that write until the reload completes, so a consent captured when it
was built would still say yes: the unload flush would ship the buffered
backlog, and the instance's fleet pinger could still ping. These tests pin the
gate that every emission point consults against the entry's current options.
"""

from __future__ import annotations

from datetime import UTC, datetime
import gzip
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki import async_unload_entry
from custom_components.hitachi_yutaki.const import (
    CONF_FLEET_PING,
    CONF_TELEMETRY_LEVEL,
    DOMAIN,
)
from custom_components.hitachi_yutaki.telemetry.consent import (
    ConfigEntryConsent,
    is_fleet_ping_enabled,
    is_telemetry_enabled,
)
from custom_components.hitachi_yutaki.telemetry.fleet_ping import FleetPinger
from custom_components.hitachi_yutaki.telemetry.http_client import (
    HttpTelemetryClient,
)
from custom_components.hitachi_yutaki.telemetry.models import (
    FleetPingUnit,
    MetricsBatch,
    SendResult,
)
from homeassistant.core import HomeAssistant

from .test_init_telemetry_identity import _make_entry, _setup

UNIT = FleetPingUnit(
    profile="yutaki_s80",
    gateway_type="modbus_atw_mbs_02",
    power_supply="three",
    has_dhw=True,
    has_pool=False,
    has_cooling=True,
    max_circuits=2,
    has_secondary_compressor=True,
)


def _mock_session(status: int = 202) -> MagicMock:
    """Session whose post() answers with the given status."""
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value="")
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock(spec=aiohttp.ClientSession)
    session.post = MagicMock(return_value=ctx)
    return session


def _revoke(hass: HomeAssistant, entry: MockConfigEntry, **extra: object) -> None:
    """Write the options the options flow writes before it schedules a reload."""
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_TELEMETRY_LEVEL: "off", **extra}
    )


class _Toggle:
    """Consent that the test flips at will."""

    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed

    def telemetry_allowed(self) -> bool:
        return self.allowed

    def fleet_ping_allowed(self) -> bool:
        return self.allowed


class TestPolicy:
    """The consent policy itself, read from an options mapping."""

    @pytest.mark.parametrize(
        ("options", "expected"),
        [
            ({}, False),
            ({CONF_TELEMETRY_LEVEL: "off"}, False),
            ({CONF_TELEMETRY_LEVEL: "on"}, True),
            ({CONF_TELEMETRY_LEVEL: "bogus"}, False),
        ],
    )
    def test_is_telemetry_enabled(self, options: dict, expected: bool) -> None:
        """Only an explicit ON consents; anything else, unknown included, is no."""
        assert is_telemetry_enabled(options) is expected

    def test_entry_consent_reads_current_options(self, hass: HomeAssistant) -> None:
        """The adapter answers from the entry's options at the time it is asked."""
        entry = MockConfigEntry(
            domain=DOMAIN, options={CONF_TELEMETRY_LEVEL: "on"}, unique_id="u1"
        )
        entry.add_to_hass(hass)
        consent = ConfigEntryConsent(entry)
        assert consent.telemetry_allowed() is True
        assert consent.fleet_ping_allowed() is True

        _revoke(hass, entry, **{CONF_FLEET_PING: False})

        assert consent.telemetry_allowed() is False
        assert consent.fleet_ping_allowed() is False
        assert is_fleet_ping_enabled(entry.options) is False


class TestHttpClientGate:
    """The HTTP client asks before every attempt, retries included."""

    @pytest.mark.asyncio
    async def test_refused_consent_sends_nothing(self) -> None:
        """No request leaves the instance once consent is withdrawn."""
        session = _mock_session()
        client = HttpTelemetryClient(session, "abc", consent=_Toggle(False))
        batch = MetricsBatch(instance_hash="abc", device_hash="d", points=[])

        assert await client.send_metrics(batch) is SendResult.NOT_CONSENTED
        session.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_withdrawal_between_retries_stops_them(self) -> None:
        """A retry scheduled before the withdrawal is not sent after it."""
        session = _mock_session(status=503)
        consent = _Toggle(True)
        client = HttpTelemetryClient(session, "abc", consent=consent)
        batch = MetricsBatch(instance_hash="abc", device_hash="d", points=[])

        async def _withdraw(_delay: float) -> None:
            consent.allowed = False

        with patch(
            "custom_components.hitachi_yutaki.telemetry.http_client.asyncio.sleep",
            side_effect=_withdraw,
        ):
            result = await client.send_metrics(batch)

        assert result is SendResult.NOT_CONSENTED
        assert session.post.call_count == 1


@pytest.mark.usefixtures("unload_entries")
class TestUnloadFlush:
    """Problem (a): the unload flush after telemetry was switched off."""

    @pytest.mark.asyncio
    async def test_unload_after_opt_out_sends_no_backlog(
        self, hass: HomeAssistant
    ) -> None:
        """Options say OFF when the reload unloads: the backlog is not sent."""
        session = _mock_session()
        entry = _make_entry(title="PAC", unique_id=f"{DOMAIN}_HW1_1", telemetry="on")
        with patch(
            "custom_components.hitachi_yutaki.async_get_clientsession",
            return_value=session,
        ):
            coordinator = await _setup(hass, entry)
        coordinator.telemetry_collector.collect(
            {"is_available": True, "outdoor_temp": 7.0}
        )
        assert coordinator.telemetry_collector.buffer_size == 1

        _revoke(hass, entry)
        with patch.object(
            hass.config_entries,
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ):
            assert await async_unload_entry(hass, entry) is True

        session.post.assert_not_called()
        # The refused batch is dropped, not counted as a failure nor re-queued.
        assert coordinator.telemetry_send_failures == 0
        assert coordinator.telemetry_collector.buffer_size == 0

    @pytest.mark.asyncio
    async def test_unload_with_consent_still_flushes(self, hass: HomeAssistant) -> None:
        """A plain reload with telemetry still ON keeps flushing the backlog."""
        session = _mock_session()
        entry = _make_entry(title="PAC", unique_id=f"{DOMAIN}_HW1_1", telemetry="on")
        with patch(
            "custom_components.hitachi_yutaki.async_get_clientsession",
            return_value=session,
        ):
            coordinator = await _setup(hass, entry)
        coordinator.telemetry_collector.collect(
            {"is_available": True, "outdoor_temp": 7.0}
        )

        with patch.object(
            hass.config_entries,
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ):
            assert await async_unload_entry(hass, entry) is True

        session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_onetime_payloads_withheld_after_opt_out(
        self, hass: HomeAssistant
    ) -> None:
        """Installation info and register snapshot ask too."""
        session = _mock_session()
        entry = _make_entry(title="PAC", unique_id=f"{DOMAIN}_HW1_1", telemetry="on")
        with patch(
            "custom_components.hitachi_yutaki.async_get_clientsession",
            return_value=session,
        ):
            coordinator = await _setup(hass, entry)
        coordinator._unit_capabilities = MagicMock(
            return_value={
                "has_dhw": True,
                "has_pool": False,
                "has_cooling": False,
                "max_circuits": 1,
                "has_secondary_compressor": False,
            }
        )

        _revoke(hass, entry)
        await coordinator._send_onetime_telemetry({"outdoor_temp": 7.0})

        session.post.assert_not_called()
        assert coordinator._installation_info_sent is False
        assert coordinator._snapshot_sent is False


class TestFleetPingGate:
    """Problem (b): the pinger between the options write and the reload."""

    @pytest.mark.asyncio
    async def test_no_ping_once_entry_withdrew(self, hass: HomeAssistant) -> None:
        """Telemetry and ping both turned off: the pending ping is not sent."""
        entry = _make_entry(title="PAC", unique_id=f"{DOMAIN}_HW1_1", telemetry="on")
        entry.add_to_hass(hass)
        session = _mock_session()
        pinger = FleetPinger(hass, session, "2.2.0")
        await pinger.async_start()
        pinger.register(entry.entry_id, lambda: UNIT, ConfigEntryConsent(entry))

        _revoke(hass, entry, **{CONF_FLEET_PING: False})

        assert await pinger.async_maybe_send() is False
        session.post.assert_not_called()
        pinger.async_stop()

    @pytest.mark.asyncio
    async def test_only_consenting_units_are_listed(self, hass: HomeAssistant) -> None:
        """A withdrawn entry drops out; the others are still counted."""
        session = _mock_session()
        pinger = FleetPinger(hass, session, "2.2.0")
        await pinger.async_start()
        pinger.register("kept", lambda: UNIT, _Toggle(True))
        pinger.register("left", lambda: UNIT, _Toggle(False))

        with patch(
            "custom_components.hitachi_yutaki.telemetry.fleet_ping.dt_util.utcnow",
            return_value=datetime(2026, 11, 24, 12, tzinfo=UTC),
        ):
            assert await pinger.async_maybe_send() is True

        payload = session.post.call_args.kwargs["data"]
        assert len(json.loads(gzip.decompress(payload))["units"]) == 1
        pinger.async_stop()
