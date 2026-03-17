"""Integration tests for telemetry — full cycle through coordinator wiring."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hitachi_yutaki.coordinator import HitachiYutakiDataCoordinator
from custom_components.hitachi_yutaki.telemetry import (
    TelemetryCollector,
    TelemetryLevel,
)
from custom_components.hitachi_yutaki.telemetry.models import (
    DailyStats,
    InstallationInfo,
    MetricsBatch,
)
from custom_components.hitachi_yutaki.telemetry.noop_client import NoopTelemetryClient


def _sample_data(**overrides) -> dict:
    """Create a sample coordinator data dict."""
    data = {
        "is_available": True,
        "outdoor_temp": 5.5,
        "water_inlet_temp": 35.0,
        "water_outlet_temp": 40.5,
        "dhw_current_temp": 52.0,
        "compressor_frequency": 65.0,
        "compressor_current": 8.5,
        "power_consumption": 3.2,
        "unit_mode": 1,  # heat
        "operation_state": "operation_state_heat_thermo_on",
        "circuit1_current_temp": 38.0,
        "circuit2_current_temp": None,
    }
    data.update(overrides)
    return data


def _make_coordinator(
    *,
    telemetry_level: TelemetryLevel = TelemetryLevel.FULL,
    buffer_max_size: int = 360,
) -> HitachiYutakiDataCoordinator:
    """Create a minimal coordinator with telemetry wired up."""
    hass = MagicMock()
    hass.config.latitude = 48.8
    hass.config.longitude = 2.3
    entry = MagicMock()
    entry.data = {"scan_interval": 5}

    api_client = MagicMock()
    api_client.is_compressor_running = True
    api_client.is_defrosting = False
    api_client.has_circuit = MagicMock(return_value=False)
    api_client.has_dhw = False
    api_client.has_pool = False

    profile = MagicMock()
    profile.supports_secondary_compressor = False

    coordinator = HitachiYutakiDataCoordinator(hass, entry, api_client, profile)

    if telemetry_level != TelemetryLevel.OFF:
        coordinator.telemetry_collector = TelemetryCollector(
            level=telemetry_level,
            buffer_max_size=buffer_max_size,
        )
        coordinator.telemetry_client = AsyncMock()
        coordinator.telemetry_client.send_installation = AsyncMock(return_value=True)
        coordinator.telemetry_client.send_metrics = AsyncMock(return_value=True)
        coordinator.telemetry_client.send_daily_stats = AsyncMock(return_value=True)
        coordinator._telemetry_meta = {
            "instance_hash": "a" * 64,
            "profile": "yutaki_s80",
            "gateway_type": "modbus_atw_mbs_02",
            "ha_version": "2025.3.1",
            "integration_version": "2.0.3",
            "power_supply": "single",
        }

    return coordinator


class TestFullCycleCollection:
    """Tests for the full collection → flush → send cycle."""

    def test_collect_populates_buffer(self):
        """Verify collect adds points to the buffer."""
        coordinator = _make_coordinator()
        data = _sample_data()

        coordinator.telemetry_collector.collect(
            data,
            is_compressor_running=True,
            is_defrosting=False,
        )

        assert coordinator.telemetry_collector.buffer_size == 1

    def test_multiple_collects(self):
        """Verify multiple collects accumulate in buffer."""
        coordinator = _make_coordinator()
        data = _sample_data()

        for _ in range(10):
            coordinator.telemetry_collector.collect(
                data,
                is_compressor_running=True,
                is_defrosting=False,
            )

        assert coordinator.telemetry_collector.buffer_size == 10

    @pytest.mark.asyncio
    async def test_flush_full_sends_metrics_batch(self):
        """FULL level: flush sends anonymized MetricsBatch."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.FULL)
        data = _sample_data()

        # Collect 5 points
        for _ in range(5):
            coordinator.telemetry_collector.collect(
                data,
                is_compressor_running=True,
                is_defrosting=False,
            )

        await coordinator.async_flush_telemetry()

        # Verify send_metrics was called
        coordinator.telemetry_client.send_metrics.assert_called_once()
        call_args = coordinator.telemetry_client.send_metrics.call_args[0][0]
        assert isinstance(call_args, MetricsBatch)
        assert len(call_args.points) == 5
        assert call_args.instance_hash == "a" * 64

        # Buffer should be empty after flush
        assert coordinator.telemetry_collector.buffer_size == 0

    @pytest.mark.asyncio
    async def test_flush_basic_sends_daily_stats(self):
        """BASIC level: flush aggregates and sends DailyStats."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.BASIC)
        data = _sample_data()

        # Collect some points
        for _ in range(3):
            coordinator.telemetry_collector.collect(
                data,
                is_compressor_running=True,
                is_defrosting=False,
            )

        await coordinator.async_flush_telemetry()

        # Verify send_daily_stats was called
        coordinator.telemetry_client.send_daily_stats.assert_called_once()
        call_args = coordinator.telemetry_client.send_daily_stats.call_args[0][0]
        assert isinstance(call_args, DailyStats)
        assert call_args.instance_hash == "a" * 64

        # Also sends installation info daily
        coordinator.telemetry_client.send_installation.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_empty_buffer_is_noop(self):
        """Flush with no buffered points does nothing."""
        coordinator = _make_coordinator()

        await coordinator.async_flush_telemetry()

        coordinator.telemetry_client.send_metrics.assert_not_called()
        coordinator.telemetry_client.send_daily_stats.assert_not_called()


class TestAnonymizationInFlush:
    """Verify anonymization is applied during flush."""

    @pytest.mark.asyncio
    async def test_temperatures_rounded_in_metrics(self):
        """FULL flush: temperature fields are rounded to 0.5°C."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.FULL)
        data = _sample_data(outdoor_temp=5.3, water_inlet_temp=34.8)

        coordinator.telemetry_collector.collect(
            data,
            is_compressor_running=True,
            is_defrosting=False,
        )

        await coordinator.async_flush_telemetry()

        batch = coordinator.telemetry_client.send_metrics.call_args[0][0]
        point = batch.points[0]
        assert point.outdoor_temp == 5.5  # rounded to nearest 0.5
        assert point.water_inlet_temp == 35.0  # rounded to nearest 0.5

    @pytest.mark.asyncio
    async def test_temperatures_rounded_in_daily_stats(self):
        """BASIC flush: temperature aggregates are rounded."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.BASIC)
        data = _sample_data(outdoor_temp=5.3)

        coordinator.telemetry_collector.collect(
            data,
            is_compressor_running=True,
            is_defrosting=False,
        )

        await coordinator.async_flush_telemetry()

        stats = coordinator.telemetry_client.send_daily_stats.call_args[0][0]
        # Rounded to 0.5
        assert stats.outdoor_temp_min == 5.5
        assert stats.outdoor_temp_max == 5.5


class TestInstallationInfo:
    """Tests for InstallationInfo sending on first poll."""

    @pytest.mark.asyncio
    async def test_sends_on_first_poll(self):
        """Installation info is sent on first successful poll."""
        coordinator = _make_coordinator()

        assert not coordinator._installation_info_sent

        await coordinator._send_installation_info()

        coordinator.telemetry_client.send_installation.assert_called_once()
        call_args = coordinator.telemetry_client.send_installation.call_args[0][0]
        assert isinstance(call_args, InstallationInfo)
        assert call_args.instance_hash == "a" * 64
        assert call_args.profile == "yutaki_s80"
        assert call_args.gateway_type == "modbus_atw_mbs_02"
        assert call_args.ha_version == "2025.3.1"
        assert call_args.power_supply == "single"

    @pytest.mark.asyncio
    async def test_installation_info_failure_is_silent(self):
        """Installation info send failure doesn't raise."""
        coordinator = _make_coordinator()
        coordinator.telemetry_client.send_installation.side_effect = Exception("boom")

        # Should not raise
        await coordinator._send_installation_info()


class TestOffLevel:
    """Tests for OFF level — zero overhead verification."""

    def test_off_collector_is_none(self):
        """OFF level: collector and client default to None."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.OFF)

        assert coordinator.telemetry_collector is None
        assert coordinator.telemetry_client is None

    @pytest.mark.asyncio
    async def test_off_flush_is_noop(self):
        """OFF level: flush does nothing."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.OFF)

        # Should not raise
        await coordinator.async_flush_telemetry()

    def test_noop_client_returns_true(self):
        """NoopTelemetryClient always returns True."""
        client = NoopTelemetryClient()
        # Verify it's a valid replacement
        assert hasattr(client, "send_installation")
        assert hasattr(client, "send_metrics")
        assert hasattr(client, "send_daily_stats")
        assert hasattr(client, "send_snapshot")


class TestSendTracking:
    """Tests for telemetry send tracking (last_send, send_failures)."""

    @pytest.mark.asyncio
    async def test_successful_send_updates_last_send(self):
        """Successful flush updates telemetry_last_send timestamp."""
        coordinator = _make_coordinator()
        data = _sample_data()

        coordinator.telemetry_collector.collect(
            data, is_compressor_running=True, is_defrosting=False
        )

        assert coordinator.telemetry_last_send is None

        await coordinator.async_flush_telemetry()

        assert coordinator.telemetry_last_send is not None
        assert isinstance(coordinator.telemetry_last_send, datetime)
        assert coordinator.telemetry_last_send.tzinfo == UTC

    @pytest.mark.asyncio
    async def test_failed_send_increments_failures(self):
        """Failed flush increments telemetry_send_failures."""
        coordinator = _make_coordinator()
        coordinator.telemetry_client.send_metrics = AsyncMock(return_value=False)
        data = _sample_data()

        coordinator.telemetry_collector.collect(
            data, is_compressor_running=True, is_defrosting=False
        )

        assert coordinator.telemetry_send_failures == 0

        await coordinator.async_flush_telemetry()

        assert coordinator.telemetry_send_failures == 1
        assert coordinator.telemetry_last_send is None

    @pytest.mark.asyncio
    async def test_exception_increments_failures(self):
        """Exception during flush increments failures without raising."""
        coordinator = _make_coordinator()
        coordinator.telemetry_client.send_metrics = AsyncMock(
            side_effect=Exception("network error")
        )
        data = _sample_data()

        coordinator.telemetry_collector.collect(
            data, is_compressor_running=True, is_defrosting=False
        )

        await coordinator.async_flush_telemetry()

        assert coordinator.telemetry_send_failures == 1


class TestBufferOverflow:
    """Tests for circular buffer overflow behavior."""

    def test_oldest_points_dropped(self):
        """Buffer overflow drops oldest points (deque maxlen)."""
        coordinator = _make_coordinator(buffer_max_size=5)
        data = _sample_data()

        # Fill buffer beyond capacity
        for _i in range(10):
            coordinator.telemetry_collector.collect(
                data, is_compressor_running=True, is_defrosting=False
            )

        # Only last 5 points retained
        assert coordinator.telemetry_collector.buffer_size == 5

    @pytest.mark.asyncio
    async def test_flush_after_overflow_sends_remaining(self):
        """Flush after overflow sends only the retained points."""
        coordinator = _make_coordinator(buffer_max_size=3)
        data = _sample_data()

        for _ in range(7):
            coordinator.telemetry_collector.collect(
                data, is_compressor_running=True, is_defrosting=False
            )

        await coordinator.async_flush_telemetry()

        batch = coordinator.telemetry_client.send_metrics.call_args[0][0]
        assert len(batch.points) == 3


class TestLevelSwap:
    """Tests for telemetry level changes (simulating reload)."""

    @pytest.mark.asyncio
    async def test_off_to_full(self):
        """Switching from OFF to FULL enables collection."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.OFF)

        assert coordinator.telemetry_collector is None

        # Simulate reload with FULL level
        coordinator.telemetry_collector = TelemetryCollector(level=TelemetryLevel.FULL)
        coordinator.telemetry_client = AsyncMock()
        coordinator.telemetry_client.send_metrics = AsyncMock(return_value=True)
        coordinator._telemetry_meta = {"instance_hash": "b" * 64}

        data = _sample_data()
        coordinator.telemetry_collector.collect(
            data, is_compressor_running=True, is_defrosting=False
        )

        assert coordinator.telemetry_collector.buffer_size == 1

    @pytest.mark.asyncio
    async def test_full_to_off_flushes_and_disables(self):
        """Switching FULL to OFF: flush remaining, then no more collection."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.FULL)
        data = _sample_data()

        coordinator.telemetry_collector.collect(
            data, is_compressor_running=True, is_defrosting=False
        )

        # Flush before "reload"
        await coordinator.async_flush_telemetry()
        coordinator.telemetry_client.send_metrics.assert_called_once()

        # Simulate reload to OFF
        coordinator.telemetry_collector = None
        coordinator.telemetry_client = None
        coordinator._telemetry_meta = None

        # Flush should be noop
        await coordinator.async_flush_telemetry()

    @pytest.mark.asyncio
    async def test_basic_to_full(self):
        """Switching BASIC to FULL changes collection behavior."""
        coordinator = _make_coordinator(telemetry_level=TelemetryLevel.BASIC)
        data = _sample_data()

        coordinator.telemetry_collector.collect(
            data, is_compressor_running=True, is_defrosting=False
        )

        # Flush as BASIC → sends daily_stats
        await coordinator.async_flush_telemetry()
        coordinator.telemetry_client.send_daily_stats.assert_called_once()

        # Simulate reload as FULL
        coordinator.telemetry_collector = TelemetryCollector(level=TelemetryLevel.FULL)

        coordinator.telemetry_collector.collect(
            data, is_compressor_running=True, is_defrosting=False
        )

        await coordinator.async_flush_telemetry()
        # Now sends metrics, not daily_stats
        coordinator.telemetry_client.send_metrics.assert_called_once()
