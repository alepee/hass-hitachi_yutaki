"""Tests for the circuit Room temperature number."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hitachi_yutaki.const import (
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
)
from custom_components.hitachi_yutaki.entities.base.number import HitachiYutakiNumber
from custom_components.hitachi_yutaki.entities.circuit.numbers import (
    _build_circuit_number_descriptions,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo


def _description(circuit_id, key):
    return next(
        d for d in _build_circuit_number_descriptions(circuit_id) if d.key == key
    )


@pytest.mark.parametrize("circuit_id", [CIRCUIT_PRIMARY_ID, CIRCUIT_SECONDARY_ID])
def test_room_temperature_created_where_the_map_can_write_it(circuit_id):
    """One number per circuit whose room register is writable."""
    number = _description(circuit_id, "room_temperature")
    coordinator = MagicMock()
    coordinator.api_client.can_write.side_effect = lambda key: (
        key == f"circuit{circuit_id}_current_temp"
    )
    assert number.condition(coordinator)
    coordinator.api_client.can_write.side_effect = lambda key: False
    assert not number.condition(coordinator)


@pytest.mark.asyncio
async def test_room_temperature_reads_status_and_writes_the_room_register():
    """Reads the unit's echo, writes through the same path as the action."""
    number = _description(CIRCUIT_PRIMARY_ID, "room_temperature")
    api = MagicMock()
    api.get_circuit_current_temperature.return_value = 19.5
    api.set_circuit_room_temperature = AsyncMock(return_value=True)
    assert number.get_fn(api, CIRCUIT_PRIMARY_ID) == 19.5
    assert await number.set_fn(api, CIRCUIT_PRIMARY_ID, 21.5) is True
    api.set_circuit_room_temperature.assert_awaited_once_with(CIRCUIT_PRIMARY_ID, 21.5)
    assert number.native_step == 0.5
    assert number.entity_category is None


def test_room_temperature_available_only_while_the_sensor_is_enabled():
    """Unavailable while the switch is off: a write would be silently ignored."""
    number = _description(CIRCUIT_PRIMARY_ID, "room_temperature")
    api = MagicMock()
    api.external_room_sensor_enabled.return_value = False
    assert number.available_fn(api, CIRCUIT_PRIMARY_ID) is False
    api.external_room_sensor_enabled.return_value = True
    assert number.available_fn(api, CIRCUIT_SECONDARY_ID) is True
    api.external_room_sensor_enabled.assert_called_with(CIRCUIT_SECONDARY_ID)


def _entity(api: MagicMock) -> HitachiYutakiNumber:
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "entry"
    coordinator.api_client = api
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    return HitachiYutakiNumber(
        coordinator,
        _description(CIRCUIT_PRIMARY_ID, "room_temperature"),
        DeviceInfo(identifiers={("hitachi_yutaki", "entry_circuit_1")}),
        register_prefix="circuit1",
    )


@pytest.mark.asyncio
async def test_entity_is_unavailable_while_the_sensor_is_off():
    """The entity-level availability follows the switch, after the poll health."""
    api = MagicMock()
    api.external_room_sensor_enabled.return_value = False
    entity = _entity(api)
    assert entity.available is False
    api.external_room_sensor_enabled.return_value = True
    assert entity.available is True
    entity.coordinator.last_update_success = False
    assert entity.available is False


@pytest.mark.asyncio
async def test_refused_write_raises_instead_of_passing_silently():
    """A gateway refusing the room value surfaces as an error on the action."""
    api = MagicMock()
    api.set_circuit_room_temperature = AsyncMock(return_value=False)
    entity = _entity(api)
    with pytest.raises(HomeAssistantError):
        await entity.async_set_native_value(21.5)
    entity.coordinator.async_request_refresh.assert_awaited_once()
    api.set_circuit_room_temperature.return_value = True
    await entity.async_set_native_value(21.5)
