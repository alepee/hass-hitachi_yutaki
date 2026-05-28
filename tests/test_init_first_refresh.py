"""Tests for the setup-time first_refresh tolerance to gateway_not_ready.

Covers issue #303: reloading the integration during the gateway's H-LINK
initialization window must NOT fail setup. Other ``ConfigEntryNotReady``
causes still propagate so HA retries setup normally.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hitachi_yutaki import (
    _async_first_refresh_tolerating_gateway_not_ready,
)
from homeassistant.exceptions import ConfigEntryNotReady


@pytest.mark.asyncio
async def test_first_refresh_success_returns_true():
    """A normal successful first_refresh returns True (data is fresh)."""
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock(return_value=None)
    coordinator.gateway_not_ready = False

    result = await _async_first_refresh_tolerating_gateway_not_ready(coordinator)

    assert result is True
    coordinator.async_config_entry_first_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_first_refresh_gateway_not_ready_swallows_and_returns_false():
    """Gateway_not_ready raises ConfigEntryNotReady but setup continues."""
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=ConfigEntryNotReady(
            "Gateway is not ready (initializing or desynchronized)"
        )
    )
    coordinator.gateway_not_ready = True

    result = await _async_first_refresh_tolerating_gateway_not_ready(coordinator)

    assert result is False


@pytest.mark.asyncio
async def test_first_refresh_cannot_connect_reraises():
    """A genuine connectivity failure still propagates ConfigEntryNotReady."""
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=ConfigEntryNotReady("Failed to communicate with device")
    )
    coordinator.gateway_not_ready = False

    with pytest.raises(ConfigEntryNotReady):
        await _async_first_refresh_tolerating_gateway_not_ready(coordinator)
