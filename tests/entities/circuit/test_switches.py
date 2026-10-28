"""Tests for circuit switch descriptions and their visibility conditions."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02_pre2016 import (
    AtwMbs02Pre2016RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.hc_a_mb import (
    HcAMbRegisterMap,
)
from custom_components.hitachi_yutaki.const import (
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
)
from custom_components.hitachi_yutaki.entities.circuit.switches import (
    _build_circuit_switch_descriptions,
)
from homeassistant.const import EntityCategory


def _coordinator(writable: set[str]) -> MagicMock:
    """Mock coordinator whose gateway can write exactly the given keys."""
    coordinator = MagicMock()
    coordinator.api_client.can_write.side_effect = lambda key: key in writable
    return coordinator


def _description(circuit_id, key):
    return next(
        d for d in _build_circuit_switch_descriptions(circuit_id) if d.key == key
    )


@pytest.mark.parametrize("circuit_id", [CIRCUIT_PRIMARY_ID, CIRCUIT_SECONDARY_ID])
def test_external_room_sensor_switch_gated_on_writable_flag(circuit_id):
    """The switch exists wherever the map can write the thermostat flag (#338)."""
    switch = _description(circuit_id, "external_room_sensor")
    assert switch.condition is not None
    assert switch.condition(_coordinator({f"circuit{circuit_id}_thermostat"}))
    assert not switch.condition(_coordinator(set()))
    other = 3 - circuit_id
    assert not switch.condition(_coordinator({f"circuit{other}_thermostat"}))


def test_external_room_sensor_switch_reads_and_writes_through_the_api():
    """ON means the flag is 1; writes go through the seeding API method."""
    switch = _description(CIRCUIT_PRIMARY_ID, "external_room_sensor")
    api = MagicMock()
    api.get_circuit_thermostat.return_value = True
    assert switch.get_fn(api, CIRCUIT_PRIMARY_ID) is True
    api.get_circuit_thermostat.return_value = False
    assert switch.get_fn(api, CIRCUIT_PRIMARY_ID) is False
    switch.set_fn(api, CIRCUIT_PRIMARY_ID, True)
    api.set_external_room_sensor.assert_called_once_with(CIRCUIT_PRIMARY_ID, True)


def test_external_room_sensor_switch_is_a_translated_config_entity():
    """Named from translations, under Configuration, not gated on bits 6/7."""
    switch = _description(CIRCUIT_PRIMARY_ID, "external_room_sensor")
    assert switch.translation_key == "external_room_sensor"
    assert switch.name is None
    assert switch.entity_category == EntityCategory.CONFIG


@pytest.mark.parametrize(
    "register_map",
    [AtwMbs02RegisterMap(), AtwMbs02Pre2016RegisterMap(), HcAMbRegisterMap()],
    ids=["atw_mbs_02", "atw_mbs_02_pre2016", "hc_a_mb"],
)
def test_every_map_can_write_the_circuit_1_thermostat_flag(register_map):
    """So the switch appears on every gateway; it was created on none before."""
    assert "circuit1_thermostat" in register_map.writable_keys


def test_pre2016_map_has_no_circuit_2_thermostat_flag():
    """Before Line-up 2016 the flag is global, modelled on circuit 1 (#318)."""
    assert "circuit2_thermostat" not in AtwMbs02Pre2016RegisterMap().writable_keys
    assert "circuit2_thermostat" in AtwMbs02RegisterMap().writable_keys
