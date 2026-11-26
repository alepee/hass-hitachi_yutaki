"""Tests for the telemetry flush timer, its catch-up flush, and how it stops."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hitachi_yutaki.const import DOMAIN
from custom_components.hitachi_yutaki.telemetry.flush_schedule import (
    TELEMETRY_CATCHUP_DELAY,
    TELEMETRY_FLUSH_INTERVAL,
    TelemetryFlushSchedule,
)
from homeassistant.core import HomeAssistant


def _schedule(
    hass: HomeAssistant, flush: AsyncMock, backlog: int
) -> TelemetryFlushSchedule:
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    schedule = TelemetryFlushSchedule(hass, entry, flush, lambda: backlog)
    schedule.start()
    return schedule


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, delay) -> None:
    freezer.tick(delay)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_backlog_after_delivery_schedules_a_catchup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A delivered batch that left points behind gets one early follow-up."""
    flush = AsyncMock(return_value=True)
    schedule = _schedule(hass, flush, backlog=8)

    await _advance(hass, freezer, TELEMETRY_FLUSH_INTERVAL)
    assert flush.await_count == 1
    await _advance(hass, freezer, TELEMETRY_CATCHUP_DELAY)
    assert flush.await_count == 2
    schedule.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("delivered", "backlog"),
    [(True, 0), (False, 60)],
    ids=["empty-buffer-after-delivery", "failed-send"],
)
async def test_no_catchup_without_a_delivered_backlog(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    delivered: bool,
    backlog: int,
) -> None:
    """Everything went out, or the send failed: the next regular cycle waits."""
    flush = AsyncMock(return_value=delivered)
    schedule = _schedule(hass, flush, backlog=backlog)

    await _advance(hass, freezer, TELEMETRY_FLUSH_INTERVAL)
    await _advance(hass, freezer, TELEMETRY_CATCHUP_DELAY)

    assert flush.await_count == 1
    schedule.stop()


@pytest.mark.asyncio
async def test_stop_cancels_the_pending_catchup_and_the_timer(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Stopping leaves no timer behind, catch-up included."""
    flush = AsyncMock(return_value=True)
    schedule = _schedule(hass, flush, backlog=8)
    await _advance(hass, freezer, TELEMETRY_FLUSH_INTERVAL)

    schedule.stop()
    schedule.stop()  # Idempotent: the unload and its backstop both call it.
    await _advance(hass, freezer, TELEMETRY_FLUSH_INTERVAL)

    assert flush.await_count == 1


@pytest.mark.asyncio
async def test_async_stop_waits_for_the_flush_in_flight(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The flush in flight is cancelled and over when ``async_stop`` returns."""
    started = asyncio.Event()
    cleaned_up = asyncio.Event()

    async def _never_answers() -> bool:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned_up.set()  # Where the coordinator re-queues its points.
        return True

    schedule = _schedule(hass, AsyncMock(side_effect=_never_answers), backlog=0)
    freezer.tick(TELEMETRY_FLUSH_INTERVAL)
    async_fire_time_changed(hass)
    await asyncio.wait_for(started.wait(), 1)

    await schedule.async_stop()

    assert cleaned_up.is_set()
