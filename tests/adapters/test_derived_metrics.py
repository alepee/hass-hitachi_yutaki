"""Tests for DerivedMetricsAdapter."""

from custom_components.hitachi_yutaki.adapters.derived_metrics import (
    DerivedMetricsAdapter,
)


def _sample_data(**overrides) -> dict:
    """Create a sample coordinator data dict with thermal-relevant keys."""
    data = {
        "is_available": True,
        "outdoor_temp": 5.0,
        "water_inlet_temp": 30.0,
        "water_outlet_temp": 35.0,
        "water_flow": 12.0,
        "compressor_frequency": 65.0,
        "compressor_current": 8.5,
        "unit_mode": 1,
        "operation_state": "operation_state_heat_thermo_on",
    }
    data.update(overrides)
    return data


def _make_adapter(
    *,
    has_cooling: bool = False,
    supports_secondary_compressor: bool = False,
) -> DerivedMetricsAdapter:
    """Create a minimal adapter for testing."""
    return DerivedMetricsAdapter(
        hass=None,
        config_entry_data={},
        power_supply="single",
        has_cooling=has_cooling,
        supports_secondary_compressor=supports_secondary_compressor,
    )


class TestThermalPower:
    """Tests for thermal power enrichment."""

    def test_heating_power_injected(self):
        """Thermal heating power is computed and injected into data dict."""
        adapter = _make_adapter()
        data = _sample_data()
        adapter.update(data)
        assert "thermal_power_heating" in data
        assert data["thermal_power_heating"] > 0

    def test_cooling_power_zero_when_heating(self):
        """Cooling power is 0 when outlet > inlet (heating mode)."""
        adapter = _make_adapter(has_cooling=True)
        data = _sample_data(water_outlet_temp=35.0, water_inlet_temp=30.0)
        adapter.update(data)
        assert data["thermal_power_cooling"] == 0

    def test_missing_flow_produces_zero_power(self):
        """Without water flow, thermal power should be 0."""
        adapter = _make_adapter()
        data = _sample_data(water_flow=None)
        adapter.update(data)
        assert data["thermal_power_heating"] == 0

    def test_cooling_sensors_only_with_has_cooling(self):
        """Cooling data keys should only be present when has_cooling=True."""
        adapter_no_cool = _make_adapter(has_cooling=False)
        data1 = _sample_data()
        adapter_no_cool.update(data1)
        assert "thermal_power_cooling" not in data1

        adapter_cool = _make_adapter(has_cooling=True)
        data2 = _sample_data()
        adapter_cool.update(data2)
        assert "thermal_power_cooling" in data2


class TestCoordinatorIntegration:
    """Tests for adapter integration with coordinator data flow."""

    def test_update_enriches_data_in_place(self):
        """update() mutates the data dict — no return value needed."""
        adapter = _make_adapter()
        data = _sample_data()
        original_keys = set(data.keys())
        adapter.update(data)
        assert set(data.keys()) > original_keys
        assert data["outdoor_temp"] == 5.0

    def test_update_with_missing_data_does_not_crash(self):
        """update() handles missing keys gracefully."""
        adapter = _make_adapter()
        data = {"is_available": True}
        adapter.update(data)
        assert data["thermal_power_heating"] == 0


class TestThermalEnergyRestore:
    """Tests for thermal energy state restoration."""

    def test_restore_heating_total(self):
        """restore_thermal_energy restores total heating energy."""
        adapter = _make_adapter()
        adapter.restore_thermal_energy("thermal_energy_heating_total", 42.5)
        data = _sample_data()
        adapter.update(data)
        assert data["thermal_energy_heating_total"] >= 42.5

    def test_restore_unknown_key_is_noop(self):
        """Unknown key does not crash."""
        adapter = _make_adapter()
        adapter.restore_thermal_energy("unknown_key", 100.0)  # should not raise
