"""Tests for the climate entity hvac_action resolution."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.hitachi_yutaki.entities.base.climate import (
    HitachiYutakiClimate,
)
from homeassistant.components.climate import HVACAction, HVACMode


def _make_climate(
    *,
    unit_mode: HVACMode | None = HVACMode.AUTO,
    operation_state: str | None = None,
    circuit_power: bool = True,
    is_defrosting: bool = False,
    is_compressor_running: bool = True,
    multi_circuit: bool = False,
) -> HitachiYutakiClimate:
    """Build a climate entity with a mocked coordinator/api_client.

    Bypasses ``__init__`` to avoid the full HA entity setup; only the
    attributes used by the ``hvac_action`` property are wired.
    """
    climate = HitachiYutakiClimate.__new__(HitachiYutakiClimate)

    api_client = MagicMock()
    api_client.get_circuit_power.return_value = circuit_power
    api_client.get_unit_mode.return_value = unit_mode
    api_client.get_operation_state.return_value = operation_state
    api_client.is_defrosting = is_defrosting
    api_client.is_compressor_running = is_compressor_running

    coordinator = MagicMock()
    coordinator.data = {"some": "data"}
    coordinator.api_client = api_client

    climate.coordinator = coordinator
    climate._circuit_id = 1
    climate._multi_circuit = multi_circuit

    return climate


class TestHvacAction:
    """Tests for the hvac_action property."""

    def test_auto_running_heating(self):
        """AUTO + heat operation state resolves to HEATING."""
        climate = _make_climate(
            unit_mode=HVACMode.AUTO,
            operation_state="operation_state_heat_thermo_on",
        )
        assert climate.hvac_action == HVACAction.HEATING

    def test_auto_running_cooling(self):
        """AUTO + cool operation state resolves to COOLING."""
        climate = _make_climate(
            unit_mode=HVACMode.AUTO,
            operation_state="operation_state_cool_thermo_on",
        )
        assert climate.hvac_action == HVACAction.COOLING

    def test_auto_indeterminate_operation_state(self):
        """AUTO + unknown operation state returns None (no signal)."""
        climate = _make_climate(
            unit_mode=HVACMode.AUTO,
            operation_state=None,
        )
        assert climate.hvac_action is None

    def test_explicit_heat_unchanged(self):
        """Explicit HEAT mode still resolves to HEATING."""
        climate = _make_climate(unit_mode=HVACMode.HEAT)
        assert climate.hvac_action == HVACAction.HEATING

    def test_explicit_cool_unchanged(self):
        """Explicit COOL mode still resolves to COOLING."""
        climate = _make_climate(unit_mode=HVACMode.COOL)
        assert climate.hvac_action == HVACAction.COOLING

    def test_off_returns_off(self):
        """Powered-off circuit returns OFF."""
        climate = _make_climate(circuit_power=False)
        assert climate.hvac_action == HVACAction.OFF

    def test_defrosting_returns_defrosting(self):
        """Defrosting unit returns DEFROSTING regardless of mode."""
        climate = _make_climate(
            unit_mode=HVACMode.AUTO,
            operation_state="operation_state_heat_thermo_on",
            is_defrosting=True,
        )
        assert climate.hvac_action == HVACAction.DEFROSTING

    def test_idle_when_compressor_off(self):
        """Compressor not running returns IDLE."""
        climate = _make_climate(
            unit_mode=HVACMode.AUTO,
            is_compressor_running=False,
        )
        assert climate.hvac_action == HVACAction.IDLE

    def test_no_data_returns_none(self):
        """No coordinator data returns None (entity not OFF)."""
        climate = _make_climate(unit_mode=HVACMode.HEAT)
        climate.coordinator.data = None
        assert climate.hvac_action is None
