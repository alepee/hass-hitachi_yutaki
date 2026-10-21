"""Tests for thermal energy sensor descriptions."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.hitachi_yutaki.entities.thermal.sensors import (
    _build_thermal_sensor_descriptions,
)
from homeassistant.components.sensor import SensorStateClass


def _make_coordinator(has_cooling: bool = True) -> MagicMock:
    """Build a mock coordinator with a water circuit and optional cooling."""
    coordinator = MagicMock()
    coordinator.profile.supports_water_circuit = True
    coordinator.has_circuit.return_value = has_cooling
    return coordinator


class TestThermalEnergyStateClass:
    """Energy counters must be compiled as meters by HA statistics."""

    def test_energy_counters_are_total_increasing(self):
        """Daily and total counters are TOTAL_INCREASING.

        The daily counters reset at midnight. Declared TOTAL without a
        last_reset, HA statistics recorded each reset as negative production
        equal to the whole previous day.
        """
        descriptions = {
            d.key: d for d in _build_thermal_sensor_descriptions(_make_coordinator())
        }
        for key in (
            "thermal_energy_heating_daily",
            "thermal_energy_heating_total",
            "thermal_energy_cooling_daily",
            "thermal_energy_cooling_total",
        ):
            assert descriptions[key].state_class is SensorStateClass.TOTAL_INCREASING, (
                key
            )
