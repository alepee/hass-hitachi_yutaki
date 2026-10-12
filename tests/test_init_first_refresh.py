"""Tests for the setup-time first refresh.

Setup only continues on fresh register data: entities and devices are gated on
the capabilities it carries, so a gateway still initializing its H-LINK bus, or
a poll without a valid ``system_config``, defers setup with
``ConfigEntryNotReady`` instead of building them from empty data (#404).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hitachi_yutaki import _async_first_refresh
from homeassistant.exceptions import ConfigEntryNotReady


def _coordinator(
    *,
    side_effect: Exception | None = None,
    gateway_not_ready: bool = False,
    data: dict | None = None,
) -> MagicMock:
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=side_effect)
    coordinator.gateway_not_ready = gateway_not_ready
    coordinator.data = data if data is not None else {"system_config": 0x0021}
    return coordinator


@pytest.mark.asyncio
async def test_first_refresh_success():
    """A successful first refresh with a valid system_config lets setup continue."""
    coordinator = _coordinator()

    await _async_first_refresh(coordinator)

    coordinator.async_config_entry_first_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_first_refresh_gateway_not_ready_defers_setup():
    """Gateway_not_ready defers setup instead of continuing on empty data (#404)."""
    coordinator = _coordinator(
        side_effect=ConfigEntryNotReady(
            "Gateway is not ready (initializing or desynchronized)"
        ),
        gateway_not_ready=True,
    )

    with pytest.raises(ConfigEntryNotReady, match="not ready"):
        await _async_first_refresh(coordinator)


@pytest.mark.asyncio
async def test_first_refresh_cannot_connect_reraises():
    """A genuine connectivity failure still propagates ConfigEntryNotReady."""
    coordinator = _coordinator(
        side_effect=ConfigEntryNotReady("Failed to communicate with device")
    )

    with pytest.raises(ConfigEntryNotReady, match="Failed to communicate"):
        await _async_first_refresh(coordinator)


@pytest.mark.asyncio
async def test_first_refresh_without_system_config_defers_setup():
    """A poll whose system_config was filtered (0xFFFF) or unreadable defers setup."""
    coordinator = _coordinator(data={"is_available": True, "system_config": None})

    with pytest.raises(ConfigEntryNotReady, match="system configuration"):
        await _async_first_refresh(coordinator)
