"""Tests for persisting system_config (capability flags) into entry.data.

See issue #308: COP services / device capabilities must be initialisable at
setup time *before* any first refresh, so that a reload during the gateway's
H-LINK init window does not drop cooling / DHW / pool COP services for the
session.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hitachi_yutaki.api.base import ReadResult
from custom_components.hitachi_yutaki.const import (
    CONF_CYCLING_DETECTION,
    CONF_REFRIGERANT_DETECTION,
    RESET_SOURCE_BUTTON,
    RESET_SOURCE_SERVICED,
)
from custom_components.hitachi_yutaki.coordinator import HitachiYutakiDataCoordinator
from custom_components.hitachi_yutaki.profiles.yutaki_s import YutakiSProfile
from custom_components.hitachi_yutaki.profiles.yutaki_sc_lite import YutakiScLiteProfile
from custom_components.hitachi_yutaki.profiles.yutampo_r32 import YutampoR32Profile
from custom_components.hitachi_yutaki.telemetry import (
    NoopTelemetryClient,
    TelemetryCollector,
    TelemetryLevel,
)
from homeassistant.const import CONF_SCAN_INTERVAL

_BASE_KEYS = ["system_config", "system_state"]


def _make_coordinator(initial_entry_data: dict, system_config_value: int):
    """Build a coordinator wired with read_value returning system_config_value."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    # Close the one-time telemetry coroutine immediately so we don't get
    # "coroutine was never awaited" warnings during the test.
    def _close_coro(coro):
        coro.close()

    hass.async_create_task = MagicMock(side_effect=_close_coro)

    api_client = MagicMock()
    api_client.connected = True
    api_client.read_values = AsyncMock(return_value=ReadResult.SUCCESS)
    api_client.async_verify_unit = AsyncMock(return_value=True)
    api_client.is_defrosting = False
    api_client.is_compressor_running = False
    api_client.base_keys = list(_BASE_KEYS)

    async def _read_value(key: str):
        if key == "system_config":
            return system_config_value
        return None

    api_client.read_value = AsyncMock(side_effect=_read_value)

    profile = MagicMock()
    profile.extra_register_keys = []

    entry = MagicMock()
    entry.data = dict(initial_entry_data)
    entry.data.setdefault(CONF_SCAN_INTERVAL, 5)

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        coord = HitachiYutakiDataCoordinator(hass, entry, api_client, profile)

    coord.telemetry_collector = TelemetryCollector(level=TelemetryLevel.OFF)
    coord.telemetry_client = NoopTelemetryClient()
    coord._telemetry_meta = {
        "instance_hash": "test",
        "device_hash": "test",
        "profile": "test",
        "gateway_type": "test",
        "ha_version": "test",
        "integration_version": "test",
        "power_supply": "single",
    }
    return coord, hass, entry


@pytest.mark.asyncio
async def test_coordinator_persists_system_config_on_first_successful_refresh():
    """First time we see a non-zero system_config, persist it in entry.data."""
    coord, hass, entry = _make_coordinator({}, system_config_value=0x1234)

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coord._async_update_data()

    hass.config_entries.async_update_entry.assert_called_once()
    args, kwargs = hass.config_entries.async_update_entry.call_args
    assert kwargs["data"]["system_config"] == 0x1234


@pytest.mark.asyncio
async def test_coordinator_does_not_write_when_system_config_unchanged():
    """No async_update_entry call when persisted value already matches live value."""
    coord, hass, entry = _make_coordinator(
        {"system_config": 0x1234}, system_config_value=0x1234
    )

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coord._async_update_data()

    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_coordinator_updates_persisted_value_when_changed():
    """When the live system_config differs from persisted, persist the new value."""
    coord, hass, entry = _make_coordinator(
        {"system_config": 0x1234}, system_config_value=0x5678
    )

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coord._async_update_data()

    hass.config_entries.async_update_entry.assert_called_once()
    args, kwargs = hass.config_entries.async_update_entry.call_args
    assert kwargs["data"]["system_config"] == 0x5678


@pytest.mark.asyncio
async def test_coordinator_does_not_persist_when_live_value_is_zero():
    """Guard against persisting a meaningless 0 when read returns None / 0."""
    coord, hass, entry = _make_coordinator({}, system_config_value=0)

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coord._async_update_data()

    hass.config_entries.async_update_entry.assert_not_called()


def test_coordinator_seeds_system_config_from_entry_data():
    """The coordinator exposes the persisted system_config before the first poll."""
    coord, _, _ = _make_coordinator({"system_config": 0x42}, system_config_value=0x42)
    assert coord.system_config == 0x42


def test_coordinator_defaults_system_config_to_zero():
    """Entries without persisted system_config (existing installs) default to 0."""
    coord, _, _ = _make_coordinator({}, system_config_value=0)
    assert coord.system_config == 0


@pytest.mark.parametrize(
    ("capability", "consent", "expected"),
    [
        (True, True, True),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    ],
)
def test_refrigerant_detection_active(capability, consent, expected):
    """refrigerant_detection_active is True only with both capability and consent."""
    coord, _, entry = _make_coordinator({}, system_config_value=0)
    coord.profile.supports_extended_compressor_sensors = capability
    entry.options = {CONF_REFRIGERANT_DETECTION: consent}
    assert coord.refrigerant_detection_active is expected


@pytest.mark.parametrize(
    ("profile", "configured_circuits", "expected"),
    [
        (YutampoR32Profile(), 0, 0),
        (YutakiScLiteProfile(), 1, 1),
        (YutakiSProfile(), 0, 2),
        (YutakiSProfile(), 1, 2),
        (YutakiSProfile(), 2, 2),
    ],
)
@pytest.mark.asyncio
async def test_max_circuits_is_hardware_limit_in_both_payloads(
    profile, configured_circuits, expected
):
    """Installation and fleet ping use profile limits, not enabled circuit count."""
    coord, hass, _ = _make_coordinator({}, system_config_value=0)
    coord.profile = profile
    coord.api_client.has_circuit.side_effect = lambda circuit, mode: (
        circuit <= configured_circuits and mode == "heating"
    )
    coord.api_client.has_dhw = True
    coord.api_client.has_pool = False
    coord.data = {"system_state": 0}
    coord.last_update_success = True
    hass.config.latitude = 48.85
    hass.config.longitude = 2.35
    coord.telemetry_client = AsyncMock()
    coord.telemetry_client.send_installation.return_value = True

    assert coord._unit_capabilities()["max_circuits"] == expected
    assert coord.fleet_ping_unit().max_circuits == expected
    await coord._send_installation_info()
    info = coord.telemetry_client.send_installation.call_args.args[0]
    assert info.max_circuits == expected


@pytest.mark.asyncio
async def test_poll_uses_client_keys_without_a_register_map():
    """Normal polling needs only the gateway-independent key contract."""
    coord, _, _ = _make_coordinator({}, system_config_value=0)
    del coord.api_client.register_map
    coord.profile.extra_register_keys = ["outdoor_temp"]
    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coord._async_update_data()
    coord.api_client.read_values.assert_awaited_once_with([*_BASE_KEYS, "outdoor_temp"])


@pytest.mark.parametrize(
    ("capability", "options", "expected"),
    [
        (False, {CONF_REFRIGERANT_DETECTION: True}, "unsupported"),
        (True, {}, "undecided"),
        (True, {CONF_REFRIGERANT_DETECTION: False}, "off"),
        (True, {CONF_REFRIGERANT_DETECTION: True}, "on"),
    ],
)
def test_maintenance_telemetry_refrigerant_consent(capability, options, expected):
    """The consent tells an off or unsupported detector from a missing verdict."""
    coord, _, entry = _make_coordinator({}, system_config_value=0)
    coord.profile.supports_extended_compressor_sensors = capability
    entry.options = options
    coord.derived_metrics = MagicMock(
        refrigerant_resets={RESET_SOURCE_BUTTON: 0, RESET_SOURCE_SERVICED: 0},
        refrigerant_days_since_reset=None,
    )
    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        info = coord._maintenance_telemetry()
    assert info["refrigerant_detection"] == expected
    assert info["cycling_detection"] == "off"
    assert ("refrigerant_resets_button" in info) is (expected == "on")


def test_maintenance_telemetry_reports_resets_and_dismissed_issues():
    """Active detectors report their resets and whether their issue was ignored."""
    coord, _, entry = _make_coordinator({}, system_config_value=0)
    coord.profile.supports_extended_compressor_sensors = True
    entry.options = {CONF_REFRIGERANT_DETECTION: True, CONF_CYCLING_DETECTION: True}
    coord.derived_metrics = MagicMock(
        refrigerant_resets={RESET_SOURCE_BUTTON: 2, RESET_SOURCE_SERVICED: 1},
        refrigerant_days_since_reset=12,
    )
    dismissed = MagicMock(dismissed_version="2026.10.0")
    with patch("custom_components.hitachi_yutaki.coordinator.ir") as ir_mock:
        ir_mock.async_get.return_value.async_get_issue.side_effect = (
            lambda _domain, issue_id: (
                dismissed if issue_id.startswith("refrigerant") else None
            )
        )
        info = coord._maintenance_telemetry()
    assert info == {
        "refrigerant_detection": "on",
        "cycling_detection": "on",
        "refrigerant_resets_button": 2,
        "refrigerant_resets_serviced": 1,
        "refrigerant_days_since_reset": 12,
        "refrigerant_issue_dismissed": True,
        "cycling_issue_dismissed": False,
    }
