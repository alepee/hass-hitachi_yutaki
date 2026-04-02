"""Tests for DerivedMetricsAdapter."""

from unittest.mock import MagicMock

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
    has_dhw: bool = False,
    has_pool: bool = False,
    supports_secondary_compressor: bool = False,
) -> DerivedMetricsAdapter:
    """Create a minimal adapter for testing."""
    config_entry = MagicMock()
    config_entry.data = {}
    return DerivedMetricsAdapter(
        hass=None,
        config_entry=config_entry,
        power_supply="single",
        has_cooling=has_cooling,
        has_dhw=has_dhw,
        has_pool=has_pool,
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


class TestCOP:
    """Tests for COP computation enrichment."""

    def test_cop_heating_key_injected(self):
        """COP heating keys are always present after update."""
        adapter = _make_adapter()
        data = _sample_data()
        adapter.update(data)
        assert "cop_heating" in data
        assert "cop_heating_quality" in data
        assert "cop_heating_measurements" in data
        assert "cop_heating_time_span_minutes" in data

    def test_cop_none_when_compressor_off(self):
        """COP is None when compressor is not running."""
        adapter = _make_adapter()
        data = _sample_data(compressor_frequency=0)
        adapter.update(data)
        assert data["cop_heating"] is None

    def test_electrical_power_injected(self):
        """Electrical power is computed and injected into data dict."""
        adapter = _make_adapter()
        data = _sample_data(compressor_current=8.5)
        adapter.update(data)
        assert "electrical_power" in data
        assert data["electrical_power"] > 0

    def test_electrical_power_zero_when_no_current(self):
        """Electrical power is 0 when compressor current is 0."""
        adapter = _make_adapter()
        data = _sample_data(compressor_current=0)
        adapter.update(data)
        assert data["electrical_power"] == 0

    def test_cop_cooling_only_with_has_cooling(self):
        """COP cooling keys are present only when has_cooling=True."""
        adapter_no = _make_adapter(has_cooling=False)
        data1 = _sample_data()
        adapter_no.update(data1)
        assert "cop_cooling" not in data1

        adapter_yes = _make_adapter(has_cooling=True)
        data2 = _sample_data()
        adapter_yes.update(data2)
        assert "cop_cooling" in data2

    def test_cop_dhw_only_with_has_dhw(self):
        """COP DHW keys are present only when has_dhw=True."""
        adapter_no = _make_adapter(has_dhw=False)
        data1 = _sample_data()
        adapter_no.update(data1)
        assert "cop_dhw" not in data1

        adapter_yes = _make_adapter(has_dhw=True)
        data2 = _sample_data()
        adapter_yes.update(data2)
        assert "cop_dhw" in data2

    def test_cop_pool_only_with_has_pool(self):
        """COP pool keys are present only when has_pool=True."""
        adapter_no = _make_adapter(has_pool=False)
        data1 = _sample_data()
        adapter_no.update(data1)
        assert "cop_pool" not in data1

        adapter_yes = _make_adapter(has_pool=True)
        data2 = _sample_data()
        adapter_yes.update(data2)
        assert "cop_pool" in data2

    def test_hvac_action_heating(self):
        """HVAC action is 'heating' when unit_mode is 1."""
        adapter = _make_adapter()
        data = _sample_data(unit_mode=1)
        assert adapter._get_hvac_action(data) == "heating"

    def test_hvac_action_cooling(self):
        """HVAC action is 'cooling' when unit_mode is 0."""
        adapter = _make_adapter()
        data = _sample_data(unit_mode=0)
        assert adapter._get_hvac_action(data) == "cooling"

    def test_hvac_action_auto_detects_from_delta(self):
        """HVAC action in auto mode is detected from temperature delta."""
        adapter = _make_adapter()
        data_heat = _sample_data(
            unit_mode=2, water_inlet_temp=30.0, water_outlet_temp=35.0
        )
        assert adapter._get_hvac_action(data_heat) == "heating"

        data_cool = _sample_data(
            unit_mode=2, water_inlet_temp=35.0, water_outlet_temp=30.0
        )
        assert adapter._get_hvac_action(data_cool) == "cooling"

    def test_reinit_cop_services(self):
        """_init_cop_services replaces existing services."""
        adapter = _make_adapter(has_cooling=False)
        assert "cop_cooling" not in adapter._cop_services

        adapter._init_cop_services(has_cooling=True, has_dhw=False, has_pool=False)
        assert "cop_cooling" in adapter._cop_services


class TestTiming:
    """Tests for compressor timing enrichment."""

    def test_timing_keys_injected(self):
        """Timing keys are injected into data dict after update."""
        adapter = _make_adapter()
        data = _sample_data(compressor_frequency=65.0)
        adapter.update(data)
        assert "compressor_cycle_time" in data
        assert "compressor_runtime" in data
        assert "compressor_resttime" in data

    def test_secondary_timing_only_with_secondary_compressor(self):
        """Secondary timing keys are only present when supports_secondary_compressor=True."""
        adapter_no = _make_adapter(supports_secondary_compressor=False)
        data1 = _sample_data()
        adapter_no.update(data1)
        assert "secondary_compressor_cycle_time" not in data1

        adapter_yes = _make_adapter(supports_secondary_compressor=True)
        data2 = _sample_data()
        adapter_yes.update(data2)
        assert "secondary_compressor_cycle_time" in data2


class TestEnergyAndCost:
    """Tests for energy integration and cost accumulation.

    Energy (kWh) is integrated from electrical_power (kW) × dt.
    Cost (€) is delta_energy × price when a price entity is configured.
    """

    def test_electrical_energy_accumulated(self):
        """electrical_energy_consumed increases when compressor is running."""
        adapter = _make_adapter()
        data1 = _sample_data(compressor_current=8.5)
        adapter.update(data1)
        # Simulate 5 seconds elapsed (within gap threshold)
        adapter._last_energy_time -= 5
        data2 = _sample_data(compressor_current=8.5)
        adapter.update(data2)
        assert data2["electrical_energy_consumed"] > 0

    def test_electrical_energy_zero_when_compressor_off(self):
        """electrical_energy_consumed stays at 0 when compressor is off."""
        adapter = _make_adapter()
        data1 = _sample_data(compressor_current=0)
        adapter.update(data1)
        data2 = _sample_data(compressor_current=0)
        adapter.update(data2)
        assert data2["electrical_energy_consumed"] == 0

    def test_power_consumption_not_overwritten(self):
        """power_consumption from Modbus is not overwritten by adapter."""
        adapter = _make_adapter()
        data = _sample_data(power_consumption=42.5)
        adapter.update(data)
        # power_consumption should remain the raw Modbus value
        assert data["power_consumption"] == 42.5

    def test_electricity_cost_not_injected_without_price_entity(self):
        """electricity_cost is not in data when no price entity configured."""
        adapter = _make_adapter()
        data = _sample_data(compressor_current=8.5)
        adapter.update(data)
        assert "electricity_cost" not in data

    def test_electricity_cost_accumulated_with_price_entity(self):
        """electricity_cost accumulates electrical_power * dt * price."""
        mock_hass = MagicMock()

        price_state = MagicMock()
        price_state.state = "0.18"

        config_entry = MagicMock()
        config_entry.data = {
            "electricity_price_entity": "sensor.price",
        }

        def states_get(entity_id):
            if entity_id == "sensor.price":
                return price_state
            return None  # no other external entities configured

        mock_hass.states.get = states_get

        adapter = DerivedMetricsAdapter(
            hass=mock_hass,
            config_entry=config_entry,
            power_supply="single",
        )

        # First update: sets baseline time
        data1 = _sample_data(compressor_current=8.5)
        adapter.update(data1)
        assert data1["electricity_cost"] == 0

        # Simulate several 5-second cycles to accumulate visible cost
        # At 1.76 kW and 0.18 €/kWh, need enough cycles for cost > 0.005 (rounds to 0.01)
        # 0.005 / 0.18 = 0.028 kWh → 0.028 / 1.76 = 0.016h = 57s → ~12 cycles of 5s
        for _ in range(15):
            adapter._last_energy_time -= 5
            data = _sample_data(compressor_current=8.5)
            adapter.update(data)

        assert data["electricity_cost"] > 0

    def test_electricity_cost_stalls_when_price_unavailable(self):
        """electricity_cost does not accumulate when price entity is unavailable."""
        mock_hass = MagicMock()

        price_state = MagicMock()
        price_state.state = "unavailable"

        config_entry = MagicMock()
        config_entry.data = {
            "electricity_price_entity": "sensor.price",
        }

        def states_get(entity_id):
            if entity_id == "sensor.price":
                return price_state
            return None

        mock_hass.states.get = states_get

        adapter = DerivedMetricsAdapter(
            hass=mock_hass,
            config_entry=config_entry,
            power_supply="single",
        )

        data1 = _sample_data(compressor_current=8.5)
        adapter.update(data1)
        adapter._last_energy_time -= 5
        data2 = _sample_data(compressor_current=8.5)
        adapter.update(data2)
        assert data2["electricity_cost"] == 0

    def test_electricity_cost_restore(self):
        """restore_electricity_cost restores the accumulated cost."""
        mock_hass = MagicMock()
        price_state = MagicMock()
        price_state.state = "0.18"

        config_entry = MagicMock()
        config_entry.data = {
            "electricity_price_entity": "sensor.price",
        }

        def states_get(entity_id):
            if entity_id == "sensor.price":
                return price_state
            return None

        mock_hass.states.get = states_get

        adapter = DerivedMetricsAdapter(
            hass=mock_hass,
            config_entry=config_entry,
            power_supply="single",
        )
        adapter.restore_electricity_cost(50.25)

        data = _sample_data(compressor_current=0)
        adapter.update(data)
        assert data["electricity_cost"] >= 50.25

    def test_gap_detection_skips_accumulation(self):
        """Cost is not accumulated when time gap exceeds 2x poll interval."""
        mock_hass = MagicMock()
        price_state = MagicMock()
        price_state.state = "0.18"

        config_entry = MagicMock()
        config_entry.data = {
            "electricity_price_entity": "sensor.price",
        }

        def states_get(entity_id):
            if entity_id == "sensor.price":
                return price_state
            return None

        mock_hass.states.get = states_get

        adapter = DerivedMetricsAdapter(
            hass=mock_hass,
            config_entry=config_entry,
            power_supply="single",
        )

        data1 = _sample_data(compressor_current=8.5)
        adapter.update(data1)

        # Simulate a long gap (60s >> 10s threshold)
        adapter._last_energy_time = adapter._last_energy_time - 60

        data2 = _sample_data(compressor_current=8.5)
        adapter.update(data2)
        assert data2["electricity_cost"] == 0

    def test_electrical_power_includes_secondary_compressor(self):
        """electrical_power sums primary + secondary compressor for S80."""
        adapter = _make_adapter(supports_secondary_compressor=True)
        data = _sample_data(
            compressor_current=8.5,
            secondary_compressor_current=6.0,
            secondary_compressor_frequency=50.0,
        )
        adapter.update(data)
        # Should be > primary-only power
        primary_only_adapter = _make_adapter(supports_secondary_compressor=False)
        primary_data = _sample_data(compressor_current=8.5)
        primary_only_adapter.update(primary_data)
        assert data["electrical_power"] > primary_data["electrical_power"]

    def test_cop_uses_precomputed_electrical_power(self):
        """COP service receives electrical_power pre-computed by adapter."""
        adapter = _make_adapter()
        data = _sample_data(compressor_current=8.5)
        adapter.update(data)
        # electrical_power should be in data and positive
        assert data["electrical_power"] > 0
        # COP keys should be present (uses the same electrical_power)
        assert "cop_heating" in data
