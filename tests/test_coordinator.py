"""Tests for HitachiYutakiDataCoordinator gateway sync resilience."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hitachi_yutaki.api.base import ReadResult
from custom_components.hitachi_yutaki.coordinator import HitachiYutakiDataCoordinator
from custom_components.hitachi_yutaki.telemetry import (
    NoopTelemetryClient,
    TelemetryCollector,
    TelemetryLevel,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    return hass


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    client = MagicMock()
    client.connected = True
    client.read_values = AsyncMock(return_value=ReadResult.SUCCESS)
    client.read_value = AsyncMock(return_value=None)
    client.register_map.base_keys = ["system_state"]
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
