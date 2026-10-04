"""Tests for the telemetry flush timer and its catch-up flush."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hitachi_yutaki import (
    TELEMETRY_CATCHUP_DELAY,
    TELEMETRY_FLUSH_INTERVAL,
    _schedule_telemetry_flush,
)

_MODULE = "custom_components.hitachi_yutaki"


def _setup(delivered: bool, buffered: int):
    """Wire the scheduler on mocks; return the timers and their callbacks."""
    hass = MagicMock()
    entry = MagicMock()
    coordinator = MagicMock()
    coordinator.async_flush_telemetry = AsyncMock(return_value=delivered)
    coordinator.telemetry_collector.buffer_size = buffered

    with (
        patch(f"{_MODULE}.async_track_time_interval") as track,
        patch(f"{_MODULE}.async_call_later") as call_later,
    ):
        _schedule_telemetry_flush(hass, entry, coordinator)
    flush = track.call_args[0][1]
    assert track.call_args[0][2] == TELEMETRY_FLUSH_INTERVAL
    return coordinator, entry, flush, call_later


@pytest.mark.asyncio
async def test_backlog_after_delivery_schedules_a_catchup():
    """A delivered batch that left points behind gets one early follow-up."""
    coordinator, _, flush, call_later = _setup(delivered=True, buffered=8)

    with patch(f"{_MODULE}.async_call_later", call_later):
        await flush(None)

    call_later.assert_called_once()
    assert call_later.call_args[0][1] == TELEMETRY_CATCHUP_DELAY

    catchup = call_later.call_args[0][2]
    await catchup(None)
    assert coordinator.async_flush_telemetry.await_count == 2


@pytest.mark.asyncio
async def test_empty_buffer_after_delivery_schedules_nothing():
    """The normal cycle: everything went out, no extra request."""
    _, _, flush, call_later = _setup(delivered=True, buffered=0)

    with patch(f"{_MODULE}.async_call_later", call_later):
        await flush(None)

    call_later.assert_not_called()


@pytest.mark.asyncio
async def test_failed_send_schedules_nothing():
    """A backlog left by a failure waits for the next regular cycle."""
    _, _, flush, call_later = _setup(delivered=False, buffered=60)

    with patch(f"{_MODULE}.async_call_later", call_later):
        await flush(None)

    call_later.assert_not_called()


@pytest.mark.asyncio
async def test_pending_catchup_is_cancelled_on_unload():
    """Unloading the entry must not leave a catch-up timer behind."""
    _, entry, flush, call_later = _setup(delivered=True, buffered=8)

    with patch(f"{_MODULE}.async_call_later", call_later):
        await flush(None)

    cancel_catchup = entry.async_on_unload.call_args_list[-1][0][0]
    cancel_catchup()
    call_later.return_value.assert_called_once()
