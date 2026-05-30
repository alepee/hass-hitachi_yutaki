"""Tests for the base switch entity (write-result handling and None guard)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hitachi_yutaki.entities.base.switch import (
    HitachiYutakiSwitch,
    HitachiYutakiSwitchEntityDescription,
)


def _make_switch(set_result: bool, data, register_prefix: str | None = None):
    """Build a switch entity with mocked coordinator and a controllable set_fn."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.api_client = MagicMock()
    coordinator.data = data
    coordinator.async_request_refresh = AsyncMock()

    set_fn = AsyncMock(return_value=set_result)
    description = HitachiYutakiSwitchEntityDescription(
        key="power",
        name="Power",
        get_fn=lambda api, circuit_id: True,
        set_fn=set_fn,
    )
    device_info = MagicMock()

    switch = HitachiYutakiSwitch(
        coordinator=coordinator,
        description=description,
        device_info=device_info,
        register_prefix=register_prefix,
    )
    return switch, coordinator, set_fn


@pytest.mark.asyncio
async def test_turn_on_failure_does_not_write_optimistic_state():
    """A failed write must not push an optimistic True into coordinator data."""
    switch, coordinator, _ = _make_switch(set_result=False, data={"power": False})
    with patch.object(switch, "async_write_ha_state") as write_state:
        await switch.async_turn_on()

    assert coordinator.data.get("power") is False
    coordinator.async_request_refresh.assert_awaited_once()
    write_state.assert_not_called()


@pytest.mark.asyncio
async def test_turn_off_failure_does_not_write_optimistic_state():
    """A failed write must not push an optimistic False into coordinator data."""
    switch, coordinator, _ = _make_switch(set_result=False, data={"power": True})
    with patch.object(switch, "async_write_ha_state") as write_state:
        await switch.async_turn_off()

    assert coordinator.data.get("power") is True
    coordinator.async_request_refresh.assert_awaited_once()
    write_state.assert_not_called()


@pytest.mark.asyncio
async def test_turn_on_before_first_refresh_does_not_raise():
    """Toggling on before the first poll (data is None) must not raise."""
    switch, coordinator, _ = _make_switch(set_result=True, data=None)
    with patch.object(switch, "async_write_ha_state"):
        await switch.async_turn_on()  # must not raise TypeError

    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_turn_off_before_first_refresh_does_not_raise():
    """Toggling off before the first poll (data is None) must not raise."""
    switch, coordinator, _ = _make_switch(set_result=True, data=None)
    with patch.object(switch, "async_write_ha_state"):
        await switch.async_turn_off()  # must not raise TypeError

    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_turn_on_success_syncs_state():
    """A successful write requests a refresh to re-sync from the live state."""
    switch, coordinator, set_fn = _make_switch(set_result=True, data={})
    with patch.object(switch, "async_write_ha_state"):
        await switch.async_turn_on()

    set_fn.assert_awaited_once()
    assert set_fn.await_args.args[2] is True
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_turn_off_success_syncs_state():
    """A successful write requests a refresh to re-sync from the live state."""
    switch, coordinator, set_fn = _make_switch(set_result=True, data={})
    with patch.object(switch, "async_write_ha_state"):
        await switch.async_turn_off()

    set_fn.assert_awaited_once()
    assert set_fn.await_args.args[2] is False
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_circuit_prefixed_set_fn_receives_circuit_id():
    """A circuit-prefixed switch derives and forwards the circuit id to set_fn."""
    switch, coordinator, set_fn = _make_switch(
        set_result=True, data={}, register_prefix="circuit1"
    )
    with patch.object(switch, "async_write_ha_state"):
        await switch.async_turn_on()

    assert set_fn.await_args.args[1] == 1
