"""Tests for reading stored states across the HA 2026.11 restore API change (#458)."""

from __future__ import annotations

from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache,
)

from custom_components.hitachi_yutaki import (
    _async_restore_energy_state,
    _async_restore_thermal_energy,
    _get_stored_state,
)
from custom_components.hitachi_yutaki.const import DOMAIN
from homeassistant.core import State
from homeassistant.helpers import entity_registry as er

_ENTITY_ID = "sensor.yutaki_power_consumption"


def test_recent_ha_reads_through_accessor():
    """HA 2026.11+ exposes `async_get_stored_state` and no `last_states`."""
    stored = MagicMock()
    restore_data = MagicMock(spec=["async_get_stored_state"])
    restore_data.async_get_stored_state.return_value = stored

    assert _get_stored_state(restore_data, _ENTITY_ID) is stored
    restore_data.async_get_stored_state.assert_called_once_with(_ENTITY_ID)


def test_older_ha_reads_last_states_dict():
    """Before 2026.11 only the `last_states` dict exists."""
    stored = MagicMock()
    restore_data = MagicMock(spec=["last_states"])
    restore_data.last_states = {_ENTITY_ID: stored}

    assert _get_stored_state(restore_data, _ENTITY_ID) is stored
    assert _get_stored_state(restore_data, "sensor.unknown") is None


def _register(hass, entry: MockConfigEntry, key: str, entity_id: str) -> None:
    er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_{key}",
        config_entry=entry,
        suggested_object_id=entity_id.split(".", 1)[1],
    )


async def test_energy_accumulators_restored_from_cache(hass):
    """On whichever HA version runs the suite, cached values reach the coordinator."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    _register(hass, entry, "power_consumption", _ENTITY_ID)
    _register(
        hass,
        entry,
        "thermal_energy_heating_total",
        "sensor.yutaki_thermal_energy_heating_total",
    )
    mock_restore_cache(
        hass,
        [
            State(_ENTITY_ID, "123.4"),
            State("sensor.yutaki_thermal_energy_heating_total", "unavailable"),
        ],
    )
    coordinator = MagicMock()

    await _async_restore_energy_state(hass, entry, coordinator)
    await _async_restore_thermal_energy(hass, entry, coordinator)

    coordinator.derived_metrics.restore_accumulated_energy.assert_called_once_with(
        123.4
    )
    coordinator.derived_metrics.restore_thermal_energy.assert_not_called()
