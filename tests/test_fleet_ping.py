"""Tests for the anonymous fleet ping (#468)."""

from __future__ import annotations

from datetime import timedelta
import gzip
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hitachi_yutaki.const import DOMAIN
from custom_components.hitachi_yutaki.repairs import (
    FleetPingNoticeRepairFlow,
    async_create_fix_flow,
)
from custom_components.hitachi_yutaki.telemetry.fleet_ping import (
    DATA_KEY,
    INITIAL_DELAY,
    STORE_KEY,
    FleetPinger,
    _load_koppen_lookup,
    async_register_fleet_ping,
    async_unregister_fleet_ping,
    classify_climate_zone,
    is_fleet_ping_enabled,
)
from custom_components.hitachi_yutaki.telemetry.models import FleetPing, FleetPingUnit
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

_REPO_ROOT = Path(__file__).parent.parent

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
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock(spec=aiohttp.ClientSession)
    session.post = MagicMock(return_value=ctx)
    return session


def _sent_payload(session: MagicMock) -> dict:
    """Decode the JSON body of the last post()."""
    body = session.post.call_args.kwargs["data"]
    return json.loads(gzip.decompress(body))


async def _started_pinger(hass: HomeAssistant, session: MagicMock) -> FleetPinger:
    pinger = FleetPinger(hass, session, "2.2.0")
    await pinger.async_start()
    return pinger


class TestPayload:
    """The payload carries no identifier and no location."""

    def test_to_dict(self) -> None:
        """Serialize the ping with its units."""
        ping = FleetPing(
            integration_version="2.2.0",
            ha_version="2026.10.1",
            climate_zone="Cfb",
            units=(UNIT,),
        )
        assert ping.to_dict() == {
            "type": "ping",
            "integration_version": "2.2.0",
            "ha_version": "2026.10.1",
            "climate_zone": "Cfb",
            "units": [
                {
                    "profile": "yutaki_s80",
                    "gateway_type": "modbus_atw_mbs_02",
                    "power_supply": "three",
                    "has_dhw": True,
                    "has_pool": False,
                    "has_cooling": True,
                    "max_circuits": 2,
                    "has_secondary_compressor": True,
                }
            ],
        }

    def test_no_identity_or_location_fields(self) -> None:
        """No hash, entry id or coordinates anywhere in the payload."""
        payload = json.dumps(FleetPing("2.2.0", "2026.10.1", "Cfb", (UNIT,)).to_dict())
        for forbidden in ("hash", "entry", "latitude", "longitude", "serial"):
            assert forbidden not in payload


class TestConsent:
    """Telemetry ON implies the ping; otherwise its own toggle, on by default."""

    @pytest.mark.parametrize(
        ("options", "expected"),
        [
            ({}, True),
            ({"telemetry_level": "off"}, True),
            ({"telemetry_level": "off", "fleet_ping": False}, False),
            ({"telemetry_level": "on", "fleet_ping": False}, True),
            ({"fleet_ping": True}, True),
        ],
    )
    def test_is_fleet_ping_enabled(self, options: dict, expected: bool) -> None:
        """Resolve the effective consent from the entry options."""
        assert is_fleet_ping_enabled(options) is expected


class TestClimateZone:
    """The Köppen zone is computed locally from the HA location."""

    def test_lookup(self) -> None:
        """Paris is temperate oceanic; no location gives no zone."""
        lookup = _load_koppen_lookup()
        assert classify_climate_zone(lookup, 48.85, 2.35) == "Cfb"
        assert classify_climate_zone(lookup, None, 2.35) is None
        assert classify_climate_zone(lookup, 0.0, -30.0) is None  # open ocean

    def test_table_matches_worker_copy(self) -> None:
        """The integration and the worker classify with the same table."""
        integration = (
            _REPO_ROOT / "custom_components/hitachi_yutaki/telemetry/koppen_lookup.json"
        )
        worker = _REPO_ROOT / "backend/worker/src/koppen-lookup.json"
        assert integration.read_bytes() == worker.read_bytes()


class TestFleetPinger:
    """Send at most once per UTC day, only once a unit is known."""

    async def test_sends_once_per_day(self, hass: HomeAssistant) -> None:
        """A delivered ping is not sent again the same day."""
        session = _mock_session()
        pinger = await _started_pinger(hass, session)
        pinger.register("entry1", lambda: UNIT)

        assert await pinger.async_maybe_send() is True
        assert await pinger.async_maybe_send() is False
        assert session.post.call_count == 1
        pinger.async_stop()

    async def test_payload_and_headers(self, hass: HomeAssistant) -> None:
        """No identity header, units from every registered entry."""
        hass.config.latitude, hass.config.longitude = 48.85, 2.35
        session = _mock_session()
        pinger = await _started_pinger(hass, session)
        pinger.register("entry1", lambda: UNIT)
        pinger.register("entry2", lambda: UNIT)

        await pinger.async_maybe_send()

        headers = session.post.call_args.kwargs["headers"]
        assert "X-Instance-Hash" not in headers
        payload = _sent_payload(session)
        assert payload["type"] == "ping"
        assert payload["climate_zone"] == "Cfb"
        assert payload["integration_version"] == "2.2.0"
        assert len(payload["units"]) == 2
        pinger.async_stop()

    async def test_skips_until_a_unit_has_polled(self, hass: HomeAssistant) -> None:
        """Nothing is sent while no provider has a unit to describe."""
        session = _mock_session()
        pinger = await _started_pinger(hass, session)
        assert await pinger.async_maybe_send() is False
        pinger.register("entry1", lambda: None)
        assert await pinger.async_maybe_send() is False
        session.post.assert_not_called()
        pinger.async_stop()

    async def test_failure_is_retried(self, hass: HomeAssistant) -> None:
        """A rejected ping does not count as today's."""
        session = _mock_session(status=500)
        pinger = await _started_pinger(hass, session)
        pinger.register("entry1", lambda: UNIT)

        assert await pinger.async_maybe_send() is False
        assert pinger.last_sent is None
        session.post.return_value.__aenter__.return_value.status = 202
        assert await pinger.async_maybe_send() is True
        pinger.async_stop()

    async def test_network_error_is_swallowed(self, hass: HomeAssistant) -> None:
        """A network error never escapes the pinger."""
        session = _mock_session()
        session.post.side_effect = aiohttp.ClientError("down")
        pinger = await _started_pinger(hass, session)
        pinger.register("entry1", lambda: UNIT)
        assert await pinger.async_maybe_send() is False
        pinger.async_stop()

    async def test_day_survives_restart(
        self, hass: HomeAssistant, hass_storage: dict
    ) -> None:
        """The persisted day prevents a second ping after a restart."""
        session = _mock_session()
        pinger = await _started_pinger(hass, session)
        pinger.register("entry1", lambda: UNIT)
        await pinger.async_maybe_send()
        pinger.async_stop()
        await hass.async_block_till_done()
        assert STORE_KEY in hass_storage

        restarted = await _started_pinger(hass, session)
        restarted.register("entry1", lambda: UNIT)
        assert await restarted.async_maybe_send() is False
        assert session.post.call_count == 1
        restarted.async_stop()

    async def test_next_day_sends_again(
        self, hass: HomeAssistant, freezer: FrozenDateTimeFactory
    ) -> None:
        """A new UTC day re-arms the ping."""
        freezer.move_to("2026-10-11 23:00:00+00:00")
        session = _mock_session()
        pinger = await _started_pinger(hass, session)
        pinger.register("entry1", lambda: UNIT)
        assert await pinger.async_maybe_send() is True

        freezer.move_to("2026-10-12 01:00:00+00:00")
        assert await pinger.async_maybe_send() is True
        assert session.post.call_count == 2
        pinger.async_stop()

    async def test_first_attempt_after_initial_delay(
        self, hass: HomeAssistant, freezer: FrozenDateTimeFactory
    ) -> None:
        """The timer sends the first ping once the initial delay elapsed."""
        session = _mock_session()
        pinger = await _started_pinger(hass, session)
        pinger.register("entry1", lambda: UNIT)

        freezer.tick(INITIAL_DELAY - timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        session.post.assert_not_called()

        freezer.tick(timedelta(seconds=2))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert session.post.call_count == 1
        pinger.async_stop()


class TestRegistration:
    """One pinger per instance, alive while an entry takes part."""

    async def test_lifecycle(self, hass: HomeAssistant) -> None:
        """Created on the first entry, removed with the last one."""
        with patch(
            "custom_components.hitachi_yutaki.telemetry.fleet_ping.async_get_clientsession",
            return_value=_mock_session(),
        ):
            await async_register_fleet_ping(hass, "entry1", "2.2.0", lambda: UNIT)
            pinger = hass.data[DATA_KEY]
            await async_register_fleet_ping(hass, "entry2", "2.2.0", lambda: UNIT)
            assert hass.data[DATA_KEY] is pinger

        async_unregister_fleet_ping(hass, "entry1")
        assert hass.data[DATA_KEY] is pinger
        async_unregister_fleet_ping(hass, "entry2")
        assert DATA_KEY not in hass.data

    async def test_unregister_without_pinger(self, hass: HomeAssistant) -> None:
        """Unregistering when nothing runs is a no-op."""
        async_unregister_fleet_ping(hass, "entry1")
        assert DATA_KEY not in hass.data


def _make_entry(options: dict | None = None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Hitachi Heat Pump",
        data={"name": "Hitachi Heat Pump", "profile": "yutaki_s"},
        options=options or {},
        entry_id="test_entry_id",
        version=2,
        minor_version=2,
    )


async def _repair_flow(hass: HomeAssistant, entry_id: str) -> FleetPingNoticeRepairFlow:
    issue_id = f"fleet_ping_notice_{entry_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="fleet_ping_notice",
    )
    flow = await async_create_fix_flow(hass, issue_id, None)
    assert isinstance(flow, FleetPingNoticeRepairFlow)
    flow.hass = hass
    flow.issue_id = issue_id
    flow.handler = DOMAIN
    return flow


class TestNoticeRepairFlow:
    """The one-time notice records the choice and clears itself."""

    async def test_shows_form(self, hass: HomeAssistant) -> None:
        """Init redirects to the confirm form, defaulting to on."""
        entry = _make_entry()
        entry.add_to_hass(hass)
        flow = await _repair_flow(hass, entry.entry_id)

        result = await flow.async_step_init({"issue_id": flow.issue_id})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

    async def test_keep_on(self, hass: HomeAssistant) -> None:
        """Keeping it on records the choice without reloading."""
        entry = _make_entry()
        entry.add_to_hass(hass)
        flow = await _repair_flow(hass, entry.entry_id)

        with patch.object(hass.config_entries, "async_reload") as reload:
            result = await flow.async_step_confirm({"fleet_ping": True})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options["fleet_ping"] is True
        reload.assert_not_called()
        assert ir.async_get(hass).async_get_issue(DOMAIN, flow.issue_id) is None

    async def test_turn_off(self, hass: HomeAssistant) -> None:
        """Turning it off records the choice and reloads the entry."""
        entry = _make_entry()
        entry.add_to_hass(hass)
        flow = await _repair_flow(hass, entry.entry_id)

        with patch.object(hass.config_entries, "async_reload") as reload:
            await flow.async_step_confirm({"fleet_ping": False})

        assert entry.options["fleet_ping"] is False
        reload.assert_awaited_once_with(entry.entry_id)

    async def test_orphaned_issue_is_removed(self, hass: HomeAssistant) -> None:
        """An issue whose entry is gone aborts and deletes itself."""
        flow = await _repair_flow(hass, "missing_entry")
        result = await flow.async_step_confirm()
        assert result["type"] is FlowResultType.ABORT
        assert ir.async_get(hass).async_get_issue(DOMAIN, flow.issue_id) is None
