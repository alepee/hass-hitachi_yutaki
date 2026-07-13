"""Regression tests for issue #365 - Yutampo R32 entity over-population.

A DHW-only Yutampo R32 (behind an ATW-MBS-02 gateway) must NOT expose entities
for hardware it does not have: the space-heating water circuit, its pumps, the
heating thermal-energy meters, and the extended compressor sensors (gas/liquid
temperature and expansion valve openings). The gateway reports a constant 0 for
all of those registers, so they cannot be filtered out by value; the fix gates
them on the profile's capability flags.

The register values used here come from a real anonymized telemetry snapshot
(see tests/fixtures/yutampo_r32_atw_mbs_02_snapshot.json), so this doubles as a
"replay the field data" test of the exact configuration the reporter has.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from custom_components.hitachi_yutaki.const import DEVICE_PRIMARY_COMPRESSOR
from custom_components.hitachi_yutaki.entities.compressor.sensors import (
    build_compressor_sensors,
)
from custom_components.hitachi_yutaki.entities.control_unit.binary_sensors import (
    build_control_unit_binary_sensors,
)
from custom_components.hitachi_yutaki.entities.hydraulic.binary_sensors import (
    build_hydraulic_binary_sensors,
)
from custom_components.hitachi_yutaki.entities.hydraulic.sensors import (
    build_hydraulic_sensors,
)
from custom_components.hitachi_yutaki.entities.thermal.sensors import (
    build_thermal_sensors,
)
from custom_components.hitachi_yutaki.profiles.yutampo_r32 import YutampoR32Profile

_FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "yutampo_r32_atw_mbs_02_snapshot.json"
)


def _load_registers() -> dict:
    """Return the real Yutampo R32 register snapshot used as test input."""
    payload = json.loads(_FIXTURE.read_text())
    return payload["registers"]


def _make_yutampo_coordinator() -> MagicMock:
    """Build a coordinator wired to the Yutampo R32 profile and real data."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {}
    coordinator.hass = MagicMock()
    coordinator.profile = YutampoR32Profile()
    coordinator.data = _load_registers()
    # DHW-only unit: no heating/cooling circuit is ever configured.
    coordinator.has_circuit = MagicMock(return_value=False)
    return coordinator


def _keys(entities: list) -> set[str]:
    return {e.entity_description.key for e in entities}


class TestYutampoR32DropsAbsentEntities:
    """Entities for absent hardware must not be created for a Yutampo R32."""

    def test_no_water_circuit_sensors(self):
        """Water inlet/outlet/target/flow/pump sensors are dropped."""
        keys = _keys(build_hydraulic_sensors(_make_yutampo_coordinator(), "test_entry"))
        for absent in (
            "water_inlet_temp",
            "water_outlet_temp",
            "water_outlet_2_temp",
            "water_outlet_3_temp",
            "water_target_temp",
            "water_flow",
            "pump_speed",
        ):
            assert absent not in keys

    def test_no_pump_binary_sensors(self):
        """Pump 1/2/3 running binary sensors are dropped."""
        keys = _keys(
            build_hydraulic_binary_sensors(_make_yutampo_coordinator(), "test_entry")
        )
        assert keys.isdisjoint({"pump1", "pump2", "pump3"})

    def test_no_heating_thermal_sensors(self):
        """Heating thermal power/energy meters are dropped (no space heating)."""
        keys = _keys(build_thermal_sensors(_make_yutampo_coordinator(), "test_entry"))
        assert keys.isdisjoint(
            {
                "thermal_power_heating",
                "thermal_energy_heating_daily",
                "thermal_energy_heating_total",
            }
        )

    def test_no_extended_compressor_sensors(self):
        """Gas/liquid temps and expansion valve openings are dropped."""
        keys = _keys(
            build_compressor_sensors(
                _make_yutampo_coordinator(), "test_entry", 1, DEVICE_PRIMARY_COMPRESSOR
            )
        )
        assert keys.isdisjoint(
            {
                "compressor_tg_gas_temp",
                "compressor_ti_liquid_temp",
                "compressor_evi_indoor_expansion_valve_opening",
                "compressor_evo_outdoor_expansion_valve_opening",
            }
        )

    def test_no_space_heater_binary_sensor(self):
        """The space-heating electric heater indicator is dropped."""
        keys = _keys(
            build_control_unit_binary_sensors(_make_yutampo_coordinator(), "test_entry")
        )
        assert "space_heater" not in keys


class TestYutampoR32KeepsRealEntities:
    """Entities backed by real Yutampo R32 data must still be created."""

    def test_core_compressor_sensors_kept(self):
        """Frequency, current, discharge and evaporator temps carry real data."""
        keys = _keys(
            build_compressor_sensors(
                _make_yutampo_coordinator(), "test_entry", 1, DEVICE_PRIMARY_COMPRESSOR
            )
        )
        for present in (
            "compressor_frequency",
            "compressor_current",
            "compressor_td_discharge_temp",
            "compressor_te_evaporator_temp",
        ):
            assert present in keys

    def test_compressor_timing_sensors_kept(self):
        """The Yutampo has a compressor, so cycle/run/rest timings remain."""
        keys = _keys(
            build_compressor_sensors(
                _make_yutampo_coordinator(), "test_entry", 1, DEVICE_PRIMARY_COMPRESSOR
            )
        )
        for present in (
            "compressor_cycle_time",
            "compressor_runtime",
            "compressor_resttime",
        ):
            assert present in keys

    def test_diagnostic_binary_sensors_kept(self):
        """Compressor/defrost indicators remain (real state on a Yutampo)."""
        keys = _keys(
            build_control_unit_binary_sensors(_make_yutampo_coordinator(), "test_entry")
        )
        assert {"compressor", "defrost"}.issubset(keys)
        # boiler is already gated off by supports_boiler for a Yutampo.
        assert "boiler" not in keys
