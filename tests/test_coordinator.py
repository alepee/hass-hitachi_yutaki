"""Tests for HitachiYutakiDataCoordinator gateway sync resilience."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hitachi_yutaki.api.base import ReadResult
from custom_components.hitachi_yutaki.const import (
    CONF_CYCLING_DETECTION,
    CONF_KEEP_EXTERNAL_ROOM_SENSOR,
    CONF_REFRIGERANT_DETECTION,
    DOMAIN,
)
from custom_components.hitachi_yutaki.coordinator import HitachiYutakiDataCoordinator
from custom_components.hitachi_yutaki.domain.models.cycling import CyclingStatus
from custom_components.hitachi_yutaki.domain.models.refrigerant import RefrigerantStatus
from custom_components.hitachi_yutaki.domain.services.defrost_guard import DefrostState
from custom_components.hitachi_yutaki.domain.services.refrigerant import (
    ALERT_PERSIST_DAYS,
    STALE_AFTER_DAYS,
)
from custom_components.hitachi_yutaki.telemetry import (
    NoopTelemetryClient,
    SendResult,
    TelemetryCollector,
    TelemetryLevel,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    # The fake HA instance does not schedule tasks; close background telemetry.
    hass.async_create_task.side_effect = lambda coroutine: coroutine.close()
    return hass


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    client = MagicMock()
    client.connected = True
    client.read_values = AsyncMock(return_value=ReadResult.SUCCESS)
    client.async_verify_unit = AsyncMock(return_value=True)
    client.read_value = AsyncMock(return_value=None)
    client.base_keys = ["system_state"]
    client.is_defrosting = False
    return client


@pytest.fixture
def mock_profile():
    """Create a mock heat pump profile."""
    profile = MagicMock()
    profile.extra_register_keys = []
    return profile


@pytest.fixture
def coordinator(mock_hass, mock_api_client, mock_profile):
    """Create a coordinator instance."""
    entry = MagicMock()
    entry.data = {CONF_SCAN_INTERVAL: 5}

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        coord = HitachiYutakiDataCoordinator(
            mock_hass, entry, mock_api_client, mock_profile
        )
    # Inject telemetry dependencies (noop for coordinator tests)
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
    return coord


@pytest.mark.asyncio
async def test_coordinator_raises_update_failed_on_gateway_not_ready(
    coordinator, mock_api_client
):
    """Test that UpdateFailed is raised when gateway is not ready."""
    mock_api_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY

    with (
        patch("custom_components.hitachi_yutaki.coordinator.ir"),
        pytest.raises(UpdateFailed, match="Gateway is not ready"),
    ):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_backoff_increases_interval(coordinator, mock_api_client):
    """Test that polling interval increases on repeated gateway-not-ready."""
    mock_api_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY
    normal = coordinator._normal_interval

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        # First failure: 2x
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        assert coordinator.update_interval == normal * 2

        # Second failure: 4x
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        assert coordinator.update_interval == normal * 4

        # Third failure: 8x
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        assert coordinator.update_interval == normal * 8


@pytest.mark.asyncio
async def test_coordinator_backoff_capped_at_300s(coordinator, mock_api_client):
    """Test that backoff interval is capped at 300 seconds."""
    mock_api_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        for _ in range(10):
            with pytest.raises(UpdateFailed):
                await coordinator._async_update_data()

    assert coordinator.update_interval <= timedelta(seconds=300)


@pytest.mark.asyncio
async def test_coordinator_restores_interval_on_recovery(coordinator, mock_api_client):
    """Test that interval is restored when gateway recovers."""
    normal = coordinator._normal_interval

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        # Trigger backoff
        mock_api_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY
        for _ in range(3):
            with pytest.raises(UpdateFailed):
                await coordinator._async_update_data()
        assert coordinator.update_interval > normal

        # Recovery
        mock_api_client.read_values.return_value = ReadResult.SUCCESS
        await coordinator._async_update_data()
        assert coordinator.update_interval == normal
        assert coordinator._gateway_not_ready_count == 0


@pytest.mark.asyncio
async def test_gateway_not_ready_property_false_initially(coordinator):
    """Initially the gateway is considered ready."""
    assert coordinator.gateway_not_ready is False


@pytest.mark.asyncio
async def test_gateway_not_ready_property_true_after_gateway_not_ready(
    coordinator, mock_api_client
):
    """Property reflects a recent gateway_not_ready result."""
    mock_api_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY

    with (
        patch("custom_components.hitachi_yutaki.coordinator.ir"),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()

    assert coordinator.gateway_not_ready is True


@pytest.mark.asyncio
async def test_gateway_not_ready_property_false_after_recovery(
    coordinator, mock_api_client
):
    """Property clears once the gateway poll succeeds again."""
    mock_api_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        with pytest.raises(UpdateFailed):  # noqa: SIM117
            await coordinator._async_update_data()
        assert coordinator.gateway_not_ready is True

        mock_api_client.read_values.return_value = ReadResult.SUCCESS
        await coordinator._async_update_data()

    assert coordinator.gateway_not_ready is False


# --- enrichment failure isolation (#386) ---


@pytest.mark.asyncio
async def test_enrichment_failure_returns_raw_data(
    coordinator, mock_api_client, caplog
):
    """A derived-metrics crash must not masquerade as a gateway error."""
    mock_api_client.read_value = AsyncMock(return_value=42)
    coordinator.derived_metrics = MagicMock()
    coordinator.derived_metrics.update.side_effect = KeyError("boom")

    with patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir:
        data = await coordinator._async_update_data()

    assert data["is_available"] is True
    assert data["system_state"] == 42
    mock_ir.async_create_issue.assert_not_called()
    mock_ir.async_delete_issue.assert_called_once_with(
        coordinator.hass, DOMAIN, "connection_error"
    )
    assert "returning raw poll data" in caplog.text
    assert "KeyError" in caplog.text


@pytest.mark.asyncio
async def test_refrigerant_issue_update_failure_returns_raw_data(
    coordinator, mock_api_client
):
    """A crash in the refrigerant repair-issue update is not a gateway error."""
    coordinator.derived_metrics = MagicMock()
    with (
        patch.object(
            coordinator, "_update_refrigerant_issue", side_effect=ValueError("boom")
        ),
        patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir,
    ):
        data = await coordinator._async_update_data()

    assert data["is_available"] is True
    mock_ir.async_create_issue.assert_not_called()


@pytest.mark.asyncio
async def test_telemetry_collect_failure_returns_raw_data(coordinator):
    """A crash in telemetry collection is not a gateway error."""
    coordinator.telemetry_collector = MagicMock()
    coordinator.telemetry_collector.collect.side_effect = ValueError("boom")

    with patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir:
        data = await coordinator._async_update_data()

    assert data["is_available"] is True
    mock_ir.async_create_issue.assert_not_called()


@pytest.mark.asyncio
async def test_modbus_read_values_failure_reports_connection_error(
    coordinator, mock_api_client
):
    """A real Modbus failure keeps today's semantics: issue + UpdateFailed."""
    mock_api_client.read_values = AsyncMock(side_effect=ConnectionError("dead link"))

    with (
        patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir,
        pytest.raises(UpdateFailed, match="Failed to communicate"),
    ):
        await coordinator._async_update_data()

    mock_ir.async_create_issue.assert_called_once()
    assert mock_ir.async_create_issue.call_args.args[2] == "connection_error"
    mock_ir.async_delete_issue.assert_not_called()


@pytest.mark.asyncio
async def test_modbus_mid_poll_failure_reports_connection_error(
    coordinator, mock_api_client
):
    """A per-key read failure (raw poll loop) is still a gateway error."""
    mock_api_client.read_value = AsyncMock(side_effect=OSError("read failed"))

    with (
        patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir,
        pytest.raises(UpdateFailed, match="Failed to communicate"),
    ):
        await coordinator._async_update_data()

    mock_ir.async_create_issue.assert_called_once()

    assert coordinator.gateway_not_ready is False


def _refrigerant_status(
    *,
    alert_streak: int,
    days_since_valid_data: int | None,
    last_valid_day: date | None = date(2026, 1, 20),
    status: str = "alert",
) -> RefrigerantStatus:
    """Build a minimal RefrigerantStatus for repair-issue tests."""
    return RefrigerantStatus(
        status=status,
        superheat_delta=6.0,
        exv_delta=20.0,
        evaporation_temp_delta=-3.0,
        baseline=None,
        valid_days=21,
        today_samples=0,
        alert_streak=alert_streak,
        last_valid_day=last_valid_day,
        days_since_valid_data=days_since_valid_data,
    )


@pytest.mark.asyncio
async def test_refrigerant_issue_created_fixable_when_fresh(coordinator):
    """A sustained alert on fresh data raises a fixable, non-stale issue."""
    coordinator.derived_metrics = MagicMock()
    coordinator.derived_metrics.refrigerant_status = _refrigerant_status(
        alert_streak=ALERT_PERSIST_DAYS,
        days_since_valid_data=1,
    )

    with patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir:
        coordinator._update_refrigerant_issue()

    mock_ir.async_create_issue.assert_called_once()
    kwargs = mock_ir.async_create_issue.call_args.kwargs
    assert kwargs["is_fixable"] is True
    assert kwargs["translation_key"] == "refrigerant_charge_alert"
    mock_ir.async_delete_issue.assert_not_called()


@pytest.mark.asyncio
async def test_refrigerant_issue_stale_variant_when_data_old(coordinator):
    """A sustained alert on old data uses the stale text with str placeholders."""
    coordinator.derived_metrics = MagicMock()
    coordinator.derived_metrics.refrigerant_status = _refrigerant_status(
        alert_streak=ALERT_PERSIST_DAYS,
        days_since_valid_data=STALE_AFTER_DAYS + 30,
        last_valid_day=date(2026, 1, 20),
    )

    with patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir:
        coordinator._update_refrigerant_issue()

    kwargs = mock_ir.async_create_issue.call_args.kwargs
    assert kwargs["is_fixable"] is True
    assert kwargs["translation_key"] == "refrigerant_charge_alert_stale"
    placeholders = kwargs["translation_placeholders"]
    assert placeholders["last_valid_day"] == "2026-01-20"
    assert placeholders["days_since_valid_data"] == str(STALE_AFTER_DAYS + 30)
    assert all(isinstance(v, str) for v in placeholders.values())


@pytest.mark.asyncio
async def test_refrigerant_issue_deleted_below_threshold(coordinator):
    """A streak below the persistence threshold clears any issue."""
    coordinator.derived_metrics = MagicMock()
    coordinator.derived_metrics.refrigerant_status = _refrigerant_status(
        alert_streak=ALERT_PERSIST_DAYS - 1,
        days_since_valid_data=1,
    )

    with patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir:
        coordinator._update_refrigerant_issue()

    mock_ir.async_create_issue.assert_not_called()
    mock_ir.async_delete_issue.assert_called_once()


@pytest.mark.asyncio
async def test_failed_flush_requeues_points(coordinator):
    """A rejected batch stays in the buffer for the next cycle (#395)."""
    coordinator.telemetry_collector = TelemetryCollector(TelemetryLevel.ON)
    coordinator.telemetry_collector.collect({"is_available": True, "outdoor_temp": 5.0})
    coordinator._telemetry_meta = {"instance_hash": "a" * 64, "device_hash": "b" * 64}
    coordinator.telemetry_client = AsyncMock()
    coordinator.telemetry_client.send_metrics.return_value = SendResult.FAILED

    await coordinator.async_flush_telemetry()

    assert coordinator.telemetry_collector.buffer_size == 1
    assert coordinator.telemetry_send_failures == 1


@pytest.mark.asyncio
async def test_successful_flush_does_not_requeue(coordinator):
    """A delivered batch is discarded, not resent."""
    coordinator.telemetry_collector = TelemetryCollector(TelemetryLevel.ON)
    coordinator.telemetry_collector.collect({"is_available": True, "outdoor_temp": 5.0})
    coordinator._telemetry_meta = {"instance_hash": "a" * 64, "device_hash": "b" * 64}
    coordinator.telemetry_client = AsyncMock()
    coordinator.telemetry_client.send_metrics.return_value = SendResult.SUCCESS

    await coordinator.async_flush_telemetry()

    assert coordinator.telemetry_collector.buffer_size == 0


@pytest.mark.asyncio
async def test_probably_delivered_flush_does_not_requeue(coordinator):
    """A batch the endpoint already archived must not be sent twice (#395)."""
    coordinator.telemetry_collector = TelemetryCollector(TelemetryLevel.ON)
    coordinator.telemetry_collector.collect({"is_available": True, "outdoor_temp": 5.0})
    coordinator._telemetry_meta = {"instance_hash": "a" * 64, "device_hash": "b" * 64}
    coordinator.telemetry_client = AsyncMock()
    coordinator.telemetry_client.send_metrics.return_value = (
        SendResult.PROBABLY_DELIVERED
    )

    await coordinator.async_flush_telemetry()

    assert coordinator.telemetry_collector.buffer_size == 0
    assert coordinator.telemetry_send_failures == 0


@pytest.mark.asyncio
async def test_cancelled_flush_requeues_points(coordinator):
    """A shutdown mid-send must not swallow the batch (#395).

    CancelledError derives from BaseException, so the `except Exception`
    handler never sees it and the points already popped from the buffer would
    be lost instead of waiting for the unload flush.
    """
    coordinator.telemetry_collector = TelemetryCollector(TelemetryLevel.ON)
    coordinator.telemetry_collector.collect({"is_available": True, "outdoor_temp": 5.0})
    coordinator._telemetry_meta = {"instance_hash": "a" * 64, "device_hash": "b" * 64}
    coordinator.telemetry_client = AsyncMock()
    coordinator.telemetry_client.send_metrics.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await coordinator.async_flush_telemetry()

    assert coordinator.telemetry_collector.buffer_size == 1


@pytest.mark.asyncio
async def test_a_failed_flush_requeues_its_points_only_once(coordinator):
    """The re-queue happens in one place, whatever the failure path."""
    coordinator.telemetry_collector = TelemetryCollector(TelemetryLevel.ON)
    coordinator.telemetry_collector.collect({"is_available": True, "outdoor_temp": 5.0})
    coordinator._telemetry_meta = {"instance_hash": "a" * 64, "device_hash": "b" * 64}
    coordinator.telemetry_client = AsyncMock()
    coordinator.telemetry_client.send_metrics.side_effect = RuntimeError("boom")

    await coordinator.async_flush_telemetry()

    assert coordinator.telemetry_collector.buffer_size == 1
    assert coordinator.telemetry_send_failures == 1


# --- Unit check (#476) ---


def _set_entry_id(coordinator) -> None:
    coordinator.config_entry.entry_id = "entry"


@pytest.mark.asyncio
async def test_unit_check_passes_when_the_unit_is_in_place(
    coordinator, mock_api_client
):
    """The client still reads its unit: the poll goes through, checked once a minute."""
    _set_entry_id(coordinator)

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_update_data()
        await coordinator._async_update_data()

    mock_api_client.async_verify_unit.assert_awaited_once()
    coordinator.hass.config_entries.async_schedule_reload.assert_not_called()


@pytest.mark.asyncio
async def test_unit_check_reloads_when_the_unit_moved(coordinator, mock_api_client):
    """Another unit at the client's address: fail the poll and reload."""
    _set_entry_id(coordinator)
    mock_api_client.async_verify_unit.return_value = False

    with (
        patch("custom_components.hitachi_yutaki.coordinator.ir"),
        pytest.raises(UpdateFailed, match="unit moved"),
    ):
        await coordinator._async_update_data()

    coordinator.hass.config_entries.async_schedule_reload.assert_called_once_with(
        "entry"
    )


@pytest.mark.asyncio
async def test_unit_check_rechecks_after_gateway_not_ready(
    coordinator, mock_api_client
):
    """A not-ready poll (gateway resyncing) forces a check on the next one."""
    _set_entry_id(coordinator)

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_update_data()
        mock_api_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        mock_api_client.read_values.return_value = ReadResult.SUCCESS
        await coordinator._async_update_data()

    assert mock_api_client.async_verify_unit.await_count == 2


@pytest.mark.asyncio
async def test_unit_check_rechecks_after_a_connection_loss(
    coordinator, mock_api_client
):
    """A gateway reboot drops the connection: the next good poll checks the unit."""
    _set_entry_id(coordinator)

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_update_data()
        mock_api_client.read_values.side_effect = ConnectionError("gateway reboot")
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        mock_api_client.read_values.side_effect = None
        # After the reboot, another unit sits at the client's address.
        mock_api_client.async_verify_unit.return_value = False
        with pytest.raises(UpdateFailed, match="unit moved"):
            await coordinator._async_update_data()

    coordinator.hass.config_entries.async_schedule_reload.assert_called_once_with(
        "entry"
    )


@pytest.mark.asyncio
async def test_unit_check_retries_when_it_cannot_be_made(coordinator, mock_api_client):
    """An inconclusive check is not a move, and is retried on the next poll."""
    _set_entry_id(coordinator)
    mock_api_client.async_verify_unit.return_value = None

    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_update_data()
        await coordinator._async_update_data()

    assert mock_api_client.async_verify_unit.await_count == 2
    coordinator.hass.config_entries.async_schedule_reload.assert_not_called()


def test_fallback_defrost_guard_has_infrastructure_clock(coordinator):
    """The fallback guard can enter recovery and expire without explicit timestamps."""
    assert coordinator.derived_metrics is None
    guard = coordinator.defrost_guard
    with patch(
        "custom_components.hitachi_yutaki.adapters.clock.monotonic",
        side_effect=[100.0, 101.0, 401.0],
    ):
        guard.update(True, 5.0)
        assert guard.state == DefrostState.DEFROST
        guard.update(False, None)
        assert guard.state == DefrostState.RECOVERY
        guard.update(False, None)
        assert guard.is_data_reliable


def test_derived_metrics_defrost_guard_takes_precedence(coordinator):
    """An attached metrics adapter supplies the shared guard used by entities."""
    coordinator.derived_metrics = MagicMock()
    assert coordinator.defrost_guard is coordinator.derived_metrics.defrost_guard


@pytest.mark.parametrize("verdict", ["alert", "watch", "ok", "learning", None])
def test_cycling_issue_translates_detector_verdict(coordinator, verdict):
    """The coordinator presents the domain decision without deriving a streak."""
    coordinator.config_entry.options = {CONF_CYCLING_DETECTION: True}
    coordinator.derived_metrics = MagicMock()
    coordinator.derived_metrics.cycling_status = (
        CyclingStatus(
            status=verdict,
            cycles_today=0,
            peak_starts_today=None,
            median_period_today=None,
            median_run_today=None,
            valid_days=3,
            alert_streak=3,
        )
        if verdict is not None
        else None
    )
    with patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir:
        coordinator._update_cycling_issue()
    if verdict == "alert":
        mock_ir.async_create_issue.assert_called_once()
        kwargs = mock_ir.async_create_issue.call_args.kwargs
        assert kwargs["translation_key"] == "compressor_short_cycling"
        assert kwargs["is_fixable"] is False
        assert kwargs["is_persistent"] is False
        assert kwargs["translation_placeholders"] == {"period": "15"}
        assert kwargs["learn_more_url"].endswith("docs/reference/cycling-monitoring.md")
        mock_ir.async_delete_issue.assert_not_called()
    else:
        mock_ir.async_create_issue.assert_not_called()
        mock_ir.async_delete_issue.assert_called_once()


@pytest.mark.parametrize("detector", ["refrigerant", "cycling"])
def test_no_consent_clears_warning_without_evaluating_policy(coordinator, detector):
    """Extraction preserves each detector's consent gate."""
    coordinator.config_entry.options = {}
    with (
        patch(
            f"custom_components.hitachi_yutaki.coordinator.{detector}_alert_policy"
        ) as policy,
        patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir,
    ):
        getattr(coordinator, f"_update_{detector}_issue")()
    policy.assert_not_called()
    mock_ir.async_create_issue.assert_not_called()
    mock_ir.async_delete_issue.assert_called_once()


def test_refrigerant_missing_capability_clears_warning(coordinator):
    """Consent cannot enable a refrigerant warning on an unsupported profile."""
    coordinator.config_entry.options = {CONF_REFRIGERANT_DETECTION: True}
    coordinator.profile.supports_extended_compressor_sensors = False
    with (
        patch(
            "custom_components.hitachi_yutaki.coordinator.refrigerant_alert_policy"
        ) as policy,
        patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir,
    ):
        coordinator._update_refrigerant_issue()
    policy.assert_not_called()
    mock_ir.async_create_issue.assert_not_called()
    mock_ir.async_delete_issue.assert_called_once()


def _room_api(
    mock_api_client,
    *,
    heating: set[int],
    thermostat: set[int],
    enabled: set[int],
    writable: set[str] = frozenset({"circuit1_thermostat", "circuit2_thermostat"}),
    unread: set[int] = frozenset(),
) -> None:
    mock_api_client.has_circuit.side_effect = lambda cid, mode: (
        cid in heating and mode == "heating"
    )
    mock_api_client.has_room_thermostat.side_effect = lambda cid: cid in thermostat
    mock_api_client.external_room_sensor_state.side_effect = lambda cid: (
        None if cid in unread else cid in enabled
    )
    mock_api_client.can_write.side_effect = lambda key: key in writable


def test_room_notice_raised_without_thermostat_and_sensor_off(
    coordinator, mock_api_client
):
    """No thermostat reported, switch off: the user is told once how it works."""
    _set_entry_id(coordinator)
    coordinator.config_entry.options = {}
    coordinator.system_config = 0x0001
    _room_api(mock_api_client, heating={1}, thermostat=set(), enabled=set())

    with patch("custom_components.hitachi_yutaki.coordinator.ir") as ir_mock:
        coordinator._update_external_room_sensor_notice()

    ir_mock.async_create_issue.assert_called_once()
    assert (
        ir_mock.async_create_issue.call_args.args[2]
        == "external_room_sensor_notice_entry"
    )
    assert ir_mock.async_create_issue.call_args.kwargs["is_fixable"] is True


@pytest.mark.parametrize(
    ("heating", "thermostat", "enabled"),
    [
        ({1}, {1}, set()),  # Hitachi thermostat reported
        ({1}, set(), {1}),  # external room sensor already on
        (set(), set(), set()),  # no heating circuit (cooling-only, DHW-only)
    ],
    ids=["thermostat_reported", "sensor_on", "no_heating_circuit"],
)
def test_room_notice_cleared_when_not_concerned(
    coordinator, mock_api_client, heating, thermostat, enabled
):
    """The notice clears on its own as soon as the situation no longer applies."""
    _set_entry_id(coordinator)
    coordinator.config_entry.options = {}
    coordinator.system_config = 0x0001
    _room_api(mock_api_client, heating=heating, thermostat=thermostat, enabled=enabled)

    with patch("custom_components.hitachi_yutaki.coordinator.ir") as ir_mock:
        coordinator._update_external_room_sensor_notice()

    ir_mock.async_create_issue.assert_not_called()
    ir_mock.async_delete_issue.assert_called_once()


def test_room_notice_never_returns_once_read(coordinator, mock_api_client):
    """Confirming records the choice: the notice does not come back."""
    _set_entry_id(coordinator)
    coordinator.config_entry.options = {"external_room_sensor_notice": True}
    coordinator.system_config = 0x0001
    _room_api(mock_api_client, heating={1}, thermostat=set(), enabled=set())

    with patch("custom_components.hitachi_yutaki.coordinator.ir") as ir_mock:
        coordinator._update_external_room_sensor_notice()

    ir_mock.async_create_issue.assert_not_called()
    ir_mock.async_delete_issue.assert_called_once()


def test_room_notice_only_where_the_map_can_write_the_flag(
    coordinator, mock_api_client
):
    """Circuit 2 before Line-up 2016 has no flag of its own: no notice for it."""
    _set_entry_id(coordinator)
    coordinator.config_entry.options = {}
    coordinator.system_config = 0x0002
    _room_api(
        mock_api_client,
        heating={2},
        thermostat=set(),
        enabled=set(),
        writable={"circuit1_thermostat"},
    )

    with patch("custom_components.hitachi_yutaki.coordinator.ir") as ir_mock:
        coordinator._update_external_room_sensor_notice()

    ir_mock.async_create_issue.assert_not_called()


@pytest.mark.parametrize(
    ("system_config", "unread"),
    [(0, set()), (0x0001, {1})],
    ids=["system_config_unread", "flag_unread"],
)
def test_room_notice_untouched_when_a_register_was_not_read(
    coordinator, mock_api_client, system_config, unread
):
    """A failed read must not toggle the notice: it would flap and lose an ignore."""
    _set_entry_id(coordinator)
    coordinator.config_entry.options = {}
    coordinator.system_config = system_config
    _room_api(
        mock_api_client, heating={1}, thermostat=set(), enabled=set(), unread=unread
    )

    with patch("custom_components.hitachi_yutaki.coordinator.ir") as ir_mock:
        coordinator._update_external_room_sensor_notice()

    ir_mock.async_create_issue.assert_not_called()
    ir_mock.async_delete_issue.assert_not_called()


def _target_api(mock_api_client, targets: dict[int, float | None], enabled=True):
    """Circuit 1 heating, writable target, flag ``enabled``, readings from ``targets``."""
    mock_api_client.has_circuit.side_effect = lambda cid, mode: (
        cid == 1 and mode == "heating"
    )
    mock_api_client.can_write.return_value = True
    mock_api_client.external_room_sensor_state.return_value = enabled
    mock_api_client.get_circuit_target_temperature.side_effect = targets.get
    mock_api_client.set_circuit_target_temperature = AsyncMock(return_value=True)
    mock_api_client.set_external_room_sensor = AsyncMock(return_value=True)


@pytest.mark.asyncio
async def test_room_target_restored_after_a_gateway_power_cycle(
    coordinator, mock_api_client
):
    """#511: target reads 0 with the sensor on, the last valid one is written back."""
    _set_entry_id(coordinator)
    _target_api(mock_api_client, {1: 22.0})
    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_keep_room_targets()
        mock_api_client.get_circuit_target_temperature.side_effect = {1: 0.0}.get
        await coordinator._async_keep_room_targets()

    mock_api_client.set_circuit_target_temperature.assert_awaited_once_with(1, 22.0)


@pytest.mark.asyncio
async def test_room_target_not_written_with_the_sensor_off(
    coordinator, mock_api_client
):
    """With the flag off the unit ignores the room registers: no write."""
    _set_entry_id(coordinator)
    _target_api(mock_api_client, {1: 22.0}, enabled=False)
    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_keep_room_targets()
        mock_api_client.get_circuit_target_temperature.side_effect = {1: 0.0}.get
        await coordinator._async_keep_room_targets()

    mock_api_client.set_circuit_target_temperature.assert_not_awaited()


@pytest.mark.asyncio
async def test_room_target_issue_raised_when_the_restore_never_holds(
    coordinator, mock_api_client
):
    """The unit keeps dropping the target: stop writing and tell the user."""
    _set_entry_id(coordinator)
    _target_api(mock_api_client, {1: 22.0})
    with patch("custom_components.hitachi_yutaki.coordinator.ir") as ir_mock:
        await coordinator._async_keep_room_targets()
        mock_api_client.get_circuit_target_temperature.side_effect = {1: 0.0}.get
        for _ in range(5):
            await coordinator._async_keep_room_targets()

    assert mock_api_client.set_circuit_target_temperature.await_count == 3
    assert (
        ir_mock.async_create_issue.call_args.args[2]
        == "room_target_restore_failed_entry"
    )
    assert ir_mock.async_create_issue.call_args.kwargs["translation_placeholders"] == {
        "circuits": "1"
    }


@pytest.mark.asyncio
async def test_remembered_room_target_is_saved(coordinator, mock_api_client):
    """A new valid target schedules a save, so it survives an HA restart."""
    _set_entry_id(coordinator)
    _target_api(mock_api_client, {1: 22.0})
    coordinator._room_target_store = MagicMock()
    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_keep_room_targets()
        await coordinator._async_keep_room_targets()

    coordinator._room_target_store.async_delay_save.assert_called_once()


def _keep_flag(coordinator) -> None:
    coordinator.config_entry.data = {
        **coordinator.config_entry.data,
        CONF_KEEP_EXTERNAL_ROOM_SENSOR: True,
    }


@pytest.mark.asyncio
async def test_external_room_sensor_raised_again_after_a_failed_poll(
    coordinator, mock_api_client
):
    """#511: flag off on the first good poll after a failure, with the opt-in."""
    _set_entry_id(coordinator)
    _keep_flag(coordinator)
    _target_api(mock_api_client, {1: 22.0})
    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_keep_room_targets()
        mock_api_client.read_values.side_effect = OSError("gateway rebooting")
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        mock_api_client.external_room_sensor_state.return_value = False
        await coordinator._async_keep_room_targets()

    mock_api_client.set_external_room_sensor.assert_awaited_once_with(1, True)
    mock_api_client.set_circuit_target_temperature.assert_not_awaited()


@pytest.mark.asyncio
async def test_external_room_sensor_left_off_without_the_opt_in(
    coordinator, mock_api_client
):
    """Off by default: a lowered flag is the user's business."""
    _set_entry_id(coordinator)
    _target_api(mock_api_client, {1: 22.0})
    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_keep_room_targets()
        coordinator._poll_gap = True
        mock_api_client.external_room_sensor_state.return_value = False
        await coordinator._async_keep_room_targets()

    mock_api_client.set_external_room_sensor.assert_not_awaited()


@pytest.mark.asyncio
async def test_external_room_sensor_turned_off_from_ha_stays_off(
    coordinator, mock_api_client
):
    """No failed poll in between: the switch was turned off, not reset."""
    _set_entry_id(coordinator)
    _keep_flag(coordinator)
    _target_api(mock_api_client, {1: 22.0})
    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_keep_room_targets()
        mock_api_client.external_room_sensor_state.return_value = False
        await coordinator._async_keep_room_targets()

    mock_api_client.set_external_room_sensor.assert_not_awaited()


@pytest.mark.asyncio
async def test_target_restored_before_the_flag_when_both_were_lost(
    coordinator, mock_api_client
):
    """A full power cut: the target is written first, then the flag is raised."""
    _set_entry_id(coordinator)
    _keep_flag(coordinator)
    _target_api(mock_api_client, {1: 22.0})
    calls: list[str] = []
    mock_api_client.set_circuit_target_temperature.side_effect = lambda *_: (
        calls.append("target") or True
    )
    mock_api_client.set_external_room_sensor.side_effect = lambda *_: (
        calls.append("flag") or True
    )
    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        await coordinator._async_keep_room_targets()
        coordinator._poll_gap = True
        mock_api_client.external_room_sensor_state.return_value = False
        mock_api_client.get_circuit_target_temperature.side_effect = {1: 0.0}.get
        await coordinator._async_keep_room_targets()

    assert calls == ["target", "flag"]


@pytest.mark.asyncio
async def test_external_room_sensor_issue_raised_when_the_flag_never_holds(
    coordinator, mock_api_client
):
    """The unit keeps the flag down: stop writing and tell the user."""
    _set_entry_id(coordinator)
    _keep_flag(coordinator)
    _target_api(mock_api_client, {1: 22.0})
    with patch("custom_components.hitachi_yutaki.coordinator.ir") as ir_mock:
        await coordinator._async_keep_room_targets()
        coordinator._poll_gap = True
        mock_api_client.external_room_sensor_state.return_value = False
        for _ in range(5):
            await coordinator._async_keep_room_targets()

    assert mock_api_client.set_external_room_sensor.await_count == 3
    assert (
        ir_mock.async_create_issue.call_args.args[2]
        == "external_room_sensor_restore_failed_entry"
    )
    assert ir_mock.async_create_issue.call_args.kwargs["translation_placeholders"] == {
        "circuits": "1"
    }


# --- Alarm repair issue (#457) ---


def _alarm_issue_kwargs(mock_ir):
    mock_ir.async_create_issue.assert_called_once()
    return mock_ir.async_create_issue.call_args.kwargs


def test_alarm_issue_raised_with_code_and_start_time(coordinator):
    """An alarm raises a non-fixable issue naming the code and its start time."""
    _set_entry_id(coordinator)
    coordinator.api_client.outdoor_link_lost = False
    with patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir:
        coordinator._update_alarm_issue("alarm_code_42")

    kwargs = _alarm_issue_kwargs(mock_ir)
    assert mock_ir.async_create_issue.call_args.args[2] == "unit_alarm_entry"
    assert kwargs["translation_key"] == "unit_alarm"
    assert kwargs["is_fixable"] is False
    assert kwargs["is_persistent"] is False
    assert kwargs["translation_placeholders"]["code"] == "42"
    assert kwargs["translation_placeholders"]["since"]


def test_alarm_issue_explains_outdoor_link_loss(coordinator):
    """Alarm 03 uses the dedicated text about the lost outdoor unit."""
    coordinator.api_client.outdoor_link_lost = True
    with patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir:
        coordinator._update_alarm_issue("alarm_code_3")

    kwargs = _alarm_issue_kwargs(mock_ir)
    assert kwargs["translation_key"] == "unit_alarm_outdoor_link"
    assert kwargs["translation_placeholders"]["code"] == "3"


def test_alarm_issue_keeps_start_time_while_alarm_lasts(coordinator):
    """Later polls of the same alarm keep the time it was first seen."""
    coordinator.api_client.outdoor_link_lost = False
    first = datetime(2026, 10, 28, 9, 0)
    later = datetime(2026, 10, 28, 9, 5)
    with (
        patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir,
        patch(
            "custom_components.hitachi_yutaki.coordinator.dt_util.now",
            side_effect=[first, later],
        ),
    ):
        coordinator._update_alarm_issue("alarm_code_42")
        coordinator._update_alarm_issue("alarm_code_42")
        coordinator._update_alarm_issue("alarm_code_2")

    sinces = [
        c.kwargs["translation_placeholders"]["since"]
        for c in mock_ir.async_create_issue.call_args_list
    ]
    assert sinces == ["2026-10-28 09:00", "2026-10-28 09:00", "2026-10-28 09:05"]


def test_alarm_issue_cleared_when_alarm_ends(coordinator):
    """The issue clears and the start time resets once the alarm is gone."""
    _set_entry_id(coordinator)
    coordinator.api_client.outdoor_link_lost = False
    with patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir:
        coordinator._update_alarm_issue("alarm_code_42")
        coordinator._update_alarm_issue("alarm_code_0")

    mock_ir.async_delete_issue.assert_called_once()
    assert mock_ir.async_delete_issue.call_args.args[2] == "unit_alarm_entry"
    assert coordinator._alarm_since is None


def test_alarm_issue_untouched_by_failed_read(coordinator):
    """A poll without an alarm code neither raises nor clears the issue."""
    with patch("custom_components.hitachi_yutaki.coordinator.ir") as mock_ir:
        coordinator._update_alarm_issue(None)

    mock_ir.async_create_issue.assert_not_called()
    mock_ir.async_delete_issue.assert_not_called()
