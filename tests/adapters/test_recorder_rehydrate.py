"""Tests for COP rehydration from Recorder history (issue #316).

Regression coverage: during rehydration the electrical power of each replayed
point must be reconstructed from that point's *historical* data, never from a
single live ``power_entity`` reading captured at rehydration time.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from custom_components.hitachi_yutaki.adapters.storage import recorder_rehydrate
from custom_components.hitachi_yutaki.adapters.storage.recorder_rehydrate import (
    async_replay_cop_history,
)
from custom_components.hitachi_yutaki.domain.services.electrical import (
    POWER_FACTOR,
    VOLTAGE_SINGLE_PHASE,
)
from homeassistant.util import dt as dt_util


def _state(value, when, *, unit=None):
    """Build a fake HA State-like object."""
    st = MagicMock()
    st.state = str(value)
    st.last_changed = when
    st.last_updated = when
    st.attributes = {"unit_of_measurement": unit} if unit else {}
    return st


def _thermal_calc(inlet, outlet, flow):
    """Return a positive thermal power so measurements are kept."""
    return max(outlet - inlet, 0.0) * flow * 0.001 + 1.0


@pytest.mark.asyncio
async def test_rehydration_uses_per_point_historical_power():
    """Each replayed point gets power from its own historical power_entity value.

    Two timestamps with different whole-unit power meter readings must produce
    two PowerMeasurements with *different* electrical_power, not the same live
    value stamped on both.
    """
    now = dt_util.utcnow()
    t0 = now - timedelta(minutes=20)
    t1 = now - timedelta(minutes=5)

    entity_ids = {
        "water_inlet_temp": "sensor.inlet",
        "water_outlet_temp": "sensor.outlet",
        "water_flow": "sensor.flow",
        "compressor_current": "sensor.current",
        "compressor_frequency": "sensor.freq",
        "power_entity": "sensor.unit_power",
    }

    states_map = {
        "sensor.inlet": [_state(30.0, t0), _state(30.0, t1)],
        "sensor.outlet": [_state(35.0, t0), _state(35.0, t1)],
        "sensor.flow": [_state(12.0, t0), _state(12.0, t1)],
        "sensor.current": [_state(8.0, t0), _state(8.0, t1)],
        "sensor.freq": [_state(60.0, t0), _state(60.0, t1)],
        # whole-unit power meter: 2 kW at t0, 4 kW at t1
        "sensor.unit_power": [
            _state(2000, t0, unit="W"),
            _state(4000, t1, unit="W"),
        ],
    }

    async def _fake_fetch(hass, ids, window, *, include_start_state):
        return {eid: states_map.get(eid, []) for eid in ids}

    hass = MagicMock()

    with patch.object(recorder_rehydrate, "_async_fetch_history", _fake_fetch):
        measurements = await async_replay_cop_history(
            hass=hass,
            entity_ids=entity_ids,
            thermal_calculator=_thermal_calc,
            electrical_calculator=lambda current: 999.0,  # live value, must NOT be used
            window=timedelta(minutes=30),
            measurement_interval=0,
            max_measurements=100,
        )

    powers = {m.electrical_power for m in measurements}
    # Both per-point historical readings appear: 2 kW (t0) and 4 kW (t1),
    # converted from W. The 4 kW value proves later points are NOT stamped
    # with the earlier reading.
    assert 2.0 in powers
    assert 4.0 in powers
    # The live calculator value (999) must never appear.
    assert 999.0 not in powers


@pytest.mark.asyncio
async def test_rehydration_falls_back_to_ixu_without_power_entity():
    """Without power_entity, per-point I×U estimate is used per timestamp."""
    now = dt_util.utcnow()
    t0 = now - timedelta(minutes=10)

    entity_ids = {
        "water_inlet_temp": "sensor.inlet",
        "water_outlet_temp": "sensor.outlet",
        "water_flow": "sensor.flow",
        "compressor_current": "sensor.current",
        "compressor_frequency": "sensor.freq",
    }

    states_map = {
        "sensor.inlet": [_state(30.0, t0)],
        "sensor.outlet": [_state(35.0, t0)],
        "sensor.flow": [_state(12.0, t0)],
        "sensor.current": [_state(10.0, t0)],
        "sensor.freq": [_state(60.0, t0)],
    }

    async def _fake_fetch(hass, ids, window, *, include_start_state):
        return {eid: states_map.get(eid, []) for eid in ids}

    hass = MagicMock()

    with patch.object(recorder_rehydrate, "_async_fetch_history", _fake_fetch):
        measurements = await async_replay_cop_history(
            hass=hass,
            entity_ids=entity_ids,
            thermal_calculator=_thermal_calc,
            electrical_calculator=lambda current: 999.0,
            window=timedelta(minutes=30),
            measurement_interval=0,
            max_measurements=100,
            is_three_phase=False,
        )

    expected = (VOLTAGE_SINGLE_PHASE * 10.0 * POWER_FACTOR) / 1000
    assert len(measurements) == 1
    assert measurements[0].electrical_power == pytest.approx(expected)
