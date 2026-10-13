"""Compare actual adapter COP samples with Recorder replay of the same polls."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from custom_components.hitachi_yutaki.adapters.derived_metrics import (
    DerivedMetricsAdapter,
)
from custom_components.hitachi_yutaki.adapters.storage import recorder_rehydrate
from custom_components.hitachi_yutaki.const import CONF_POWER_ENTITY
from homeassistant.core import State
from tests.domain.clock import FakeClock


def _state(value, when, unit=None):
    state = MagicMock()
    state.state = str(value)
    state.last_changed = state.last_updated = when
    state.attributes = {"unit_of_measurement": unit} if unit else {}
    return state


@pytest.mark.parametrize(
    (
        "cop_key",
        "operation_state",
        "inlet",
        "outlet",
        "current",
        "meter",
        "secondary",
        "defrost",
        "expected_count",
    ),
    [
        ("cop_heating", "heat_thermo_on", 35, 30, 5, True, False, False, 0),
        ("cop_heating", "heat_thermo_on", 30, 35, 0, True, False, False, 6),
        ("cop_heating", "heat_thermo_on", 30, 35, 0, False, False, False, 0),
        ("cop_heating", "heat_thermo_on", 30, 35, 5, True, True, False, 6),
        ("cop_heating", "heat_thermo_on", 30, 35, 5, False, True, False, 6),
        ("cop_cooling", "cool_thermo_on", 35, 30, 5, True, False, False, 6),
        ("cop_cooling", "heat_thermo_on", 35, 30, 5, True, False, False, 0),
        ("cop_dhw", "dhw_on", 35, 30, 5, True, False, False, 0),
        ("cop_dhw", "dhw_on", 30, 35, 5, True, False, False, 6),
        ("cop_pool", "pool_on", 30, 35, 5, True, False, False, 6),
        ("cop_heating", "heat_thermo_on", 30, 35, 5, True, False, True, 2),
    ],
)
async def test_live_replay_identical_samples(
    monkeypatch,
    cop_key,
    operation_state,
    inlet,
    outlet,
    current,
    meter,
    secondary,
    defrost,
    expected_count,
):
    """Share mode/sign admission, zero-current meters, S80 power and defrost gates."""
    clock = FakeClock()
    entry = MagicMock()
    entry.data = {CONF_POWER_ENTITY: "sensor.power"} if meter else {}
    hass = MagicMock()
    adapter = DerivedMetricsAdapter(
        hass,
        entry,
        "single",
        has_cooling=True,
        has_dhw=True,
        has_pool=True,
        supports_secondary_compressor=secondary,
        clock=clock,
    )
    service = adapter._cop_services[cop_key]
    raw = {
        "water_inlet_temp": inlet,
        "water_outlet_temp": outlet,
        "water_flow": 1,
        "compressor_current": current,
        "compressor_frequency": 50,
        "operation_state": f"operation_state_{operation_state}",
        "is_defrosting": False,
    }
    if secondary:
        raw.update(secondary_compressor_current=3, secondary_compressor_frequency=40)
    entity_ids = {key: f"sensor.{key}" for key in raw}
    if meter:
        entity_ids["power_entity"] = "sensor.power"
    states = {eid: [] for eid in entity_ids.values()}
    start = clock.wall
    for index in range(6):
        clock.seconds = 10000 + index * 60
        clock.wall = start + timedelta(minutes=index)
        raw["is_defrosting"] = defrost and index == 1
        if meter:
            power = _state(2000 if index == 0 else 4000, clock.wall, "W")
            states["sensor.power"].append(power)
            hass.states.get.return_value = power
        for key, value in raw.items():
            states[entity_ids[key]].append(_state(value, clock.wall))
        adapter.update(dict(raw))

    async def fetch(*_args, **_kwargs):
        return states

    monkeypatch.setattr(recorder_rehydrate, "_async_fetch_history", fetch)
    replay = await recorder_rehydrate.async_replay_cop_history(
        hass,
        entity_ids=entity_ids,
        measurement_builder=service.build_measurement,
        window=timedelta(minutes=30),
        measurement_interval=60,
        max_measurements=100,
    )
    live = service._accumulator.measurements
    assert len(live) == len(replay) == expected_count
    assert replay == live
    if live and meter:
        assert live[0].electrical_power == 2
        assert live[-1].electrical_power == 4
        assert live[0].thermal_power == pytest.approx(5.8125)


async def test_async_rehydrate_selects_mode_specific_builder(monkeypatch):
    """The production wiring passes each service's builder, including heating."""
    adapter = DerivedMetricsAdapter(
        MagicMock(), MagicMock(), "single", has_cooling=True
    )
    captured = []

    async def replay(**kwargs):
        captured.append(kwargs["measurement_builder"])
        return []

    monkeypatch.setattr(recorder_rehydrate, "async_replay_cop_history", replay)
    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get", lambda _: MagicMock()
    )
    await adapter.async_rehydrate_cop()
    assert captured == [
        service.build_measurement for service in adapter._cop_services.values()
    ]


@pytest.mark.parametrize("thermal_records", [True, False])
async def test_meter_events_do_not_end_defrost_recovery(monkeypatch, thermal_records):
    """Electrical events cannot substitute for fresh thermal observations."""
    clock = FakeClock()
    start = clock.wall
    entry = MagicMock()
    entry.data = {CONF_POWER_ENTITY: "sensor.power"}
    hass = MagicMock()
    adapter = DerivedMetricsAdapter(hass, entry, "single", clock=clock)
    service = adapter._cop_services["cop_heating"]
    raw = {
        "water_inlet_temp": 30,
        "water_outlet_temp": 35,
        "water_flow": 1,
        "compressor_current": 5,
        "compressor_frequency": 50,
        "operation_state": "operation_state_heat_thermo_on",
        "is_defrosting": False,
    }
    entity_ids = {key: f"sensor.{key}" for key in raw}
    entity_ids["power_entity"] = "sensor.power"
    states = {entity_id: [] for entity_id in entity_ids.values()}

    def record(entity_id, value, elapsed, unit=None):
        when = start + timedelta(seconds=elapsed)
        state = State(
            entity_id,
            str(value),
            {"unit_of_measurement": unit} if unit else {},
            last_changed=when,
            last_updated=when,
        )
        states[entity_id].append(state)
        return state

    for elapsed in (0, 90, 100, 105, 110, 115, 400):
        clock.seconds = 10000 + elapsed
        clock.wall = start + timedelta(seconds=elapsed)
        raw["is_defrosting"] = elapsed == 90
        hass.states.get.return_value = record(
            "sensor.power", 2000 + elapsed, elapsed, "W"
        )
        for key, value in raw.items():
            if (
                not thermal_records
                and elapsed != 0
                and key in {"water_inlet_temp", "water_outlet_temp"}
            ):
                continue
            record(entity_ids[key], value, elapsed)
        adapter.update(dict(raw))

    for elapsed in (101, 102, 103):
        record("sensor.power", 2000 + elapsed, elapsed, "W")

    async def fetch(*_args, **_kwargs):
        return states

    monkeypatch.setattr(recorder_rehydrate, "_async_fetch_history", fetch)
    replay = await recorder_rehydrate.async_replay_cop_history(
        hass,
        entity_ids=entity_ids,
        measurement_builder=service.build_measurement,
        window=timedelta(minutes=30),
        measurement_interval=60,
        max_measurements=100,
    )
    live = service._accumulator.measurements
    assert [(point.timestamp - start).total_seconds() for point in live] == [
        0,
        115,
        400,
    ]
    expected = [0, 115, 400] if thermal_records else [0, 400]
    assert [(point.timestamp - start).total_seconds() for point in replay] == expected
    if thermal_records:
        assert replay == live


async def test_partial_temperature_record_invalidates_recovery(monkeypatch):
    """A changed outlet can invalidate stability without a new inlet record."""
    clock = FakeClock()
    start = clock.wall
    entry = MagicMock()
    entry.data = {CONF_POWER_ENTITY: "sensor.power"}
    hass = MagicMock()
    adapter = DerivedMetricsAdapter(hass, entry, "single", clock=clock)
    service = adapter._cop_services["cop_heating"]
    raw = {
        "water_inlet_temp": 30,
        "water_outlet_temp": 35,
        "water_flow": 1,
        "compressor_current": 5,
        "compressor_frequency": 50,
        "operation_state": "operation_state_heat_thermo_on",
        "is_defrosting": False,
    }
    entity_ids = {key: f"sensor.{key}" for key in raw}
    entity_ids["power_entity"] = "sensor.power"
    states = {entity_id: [] for entity_id in entity_ids.values()}
    last_values = {}
    polls = (
        (0, {}),
        (90, {"is_defrosting": True}),
        (100, {"is_defrosting": False}),
        (105, {"water_inlet_temp": 31, "water_outlet_temp": 36}),
        (110, {"water_inlet_temp": 32, "water_outlet_temp": 37}),
        (115, {"water_outlet_temp": 27}),
        (120, {"water_inlet_temp": 33, "water_outlet_temp": 38}),
        (125, {"water_inlet_temp": 34, "water_outlet_temp": 39}),
        (130, {"water_inlet_temp": 35, "water_outlet_temp": 40}),
    )
    for elapsed, changes in polls:
        clock.seconds = 10000 + elapsed
        clock.wall = start + timedelta(seconds=elapsed)
        raw.update(changes)
        power = State(
            "sensor.power",
            str(2000 + elapsed),
            {"unit_of_measurement": "W"},
            last_changed=clock.wall,
            last_updated=clock.wall,
        )
        states["sensor.power"].append(power)
        hass.states.get.return_value = power
        for key, value in raw.items():
            if key in last_values and last_values[key] == value:
                continue
            states[entity_ids[key]].append(
                State(
                    entity_ids[key],
                    str(value),
                    last_changed=clock.wall,
                    last_updated=clock.wall,
                )
            )
            last_values[key] = value
        adapter.update(dict(raw))

    async def fetch(*_args, **_kwargs):
        return states

    monkeypatch.setattr(recorder_rehydrate, "_async_fetch_history", fetch)
    replay = await recorder_rehydrate.async_replay_cop_history(
        hass,
        entity_ids=entity_ids,
        measurement_builder=service.build_measurement,
        window=timedelta(minutes=30),
        measurement_interval=60,
        max_measurements=100,
    )
    live = service._accumulator.measurements
    assert [(point.timestamp - start).total_seconds() for point in live] == [0, 130]
    assert replay == live
