"""Tests for the daily re-arm of the installation telemetry payload."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hitachi_yutaki.coordinator import HitachiYutakiDataCoordinator
from custom_components.hitachi_yutaki.telemetry import (
    NoopTelemetryClient,
    TelemetryCollector,
    TelemetryLevel,
)
from homeassistant.const import CONF_SCAN_INTERVAL


@pytest.fixture
def coordinator():
    """Create a coordinator with noop telemetry."""
    hass = MagicMock()
    api_client = MagicMock()
    api_client.connected = True
    api_client.read_values = AsyncMock()
    api_client.register_map.base_keys = ["system_state"]
    profile = MagicMock()
    profile.extra_register_keys = []
    entry = MagicMock()
    entry.data = {CONF_SCAN_INTERVAL: 5}
    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        coord = HitachiYutakiDataCoordinator(hass, entry, api_client, profile)
    coord.telemetry_collector = TelemetryCollector(level=TelemetryLevel.OFF)
    coord.telemetry_client = NoopTelemetryClient()
    coord._telemetry_meta = {
        "instance_hash": "0" * 64,
        "profile": "yutaki_s",
        "gateway_type": "modbus_atw_mbs_02",
        "ha_version": "2026.5.0",
        "integration_version": "2.1.1",
        "power_supply": "single",
    }
    return coord


def test_rearm_on_new_day_resets_flag(coordinator):
    """Crossing a UTC day boundary re-arms the installation send."""
    coordinator._installation_info_sent = True
    coordinator._installation_sent_date = date(2026, 5, 24)

    coordinator._maybe_rearm_installation_resend(date(2026, 5, 25))

    assert coordinator._installation_info_sent is False


def test_no_rearm_same_day(coordinator):
    """Within the same UTC day the flag stays set."""
    coordinator._installation_info_sent = True
    coordinator._installation_sent_date = date(2026, 5, 25)

    coordinator._maybe_rearm_installation_resend(date(2026, 5, 25))

    assert coordinator._installation_info_sent is True


def test_no_rearm_before_first_send(coordinator):
    """Before any send (date is None) the flag is left untouched."""
    coordinator._installation_info_sent = False
    coordinator._installation_sent_date = None

    coordinator._maybe_rearm_installation_resend(date(2026, 5, 25))

    assert coordinator._installation_info_sent is False
    assert coordinator._installation_sent_date is None
