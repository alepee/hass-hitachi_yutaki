"""Tests for thermal power and energy services."""

from unittest.mock import patch

import pytest

from custom_components.hitachi_yutaki.domain.models.thermal import ThermalPowerInput
from custom_components.hitachi_yutaki.domain.services.thermal import (
    ThermalEnergyAccumulator,
    ThermalPowerService,
    calculate_thermal_power,
    calculate_thermal_power_cooling,
    calculate_thermal_power_heating,
)


def test_calculate_thermal_power():
    """Test pure thermal power calculation."""
    # Heating case: outlet > inlet
    # 1 m3/h * 4.185 kJ/kg.K * 0.277778 kg/s * 5K = 5.81 kW
    data = ThermalPowerInput(
        water_inlet_temp=30.0, water_outlet_temp=35.0, water_flow=1.0
    )
    power = calculate_thermal_power(data)
    assert power == pytest.approx(5.8125, rel=1e-3)

    # Cooling case: outlet < inlet
    data = ThermalPowerInput(
        water_inlet_temp=12.0, water_outlet_temp=7.0, water_flow=1.0
    )
    power = calculate_thermal_power(data)
    assert power == pytest.approx(-5.8125, rel=1e-3)


def test_calculate_thermal_power_heating():
    """Test heating specific power calculation."""
    data = ThermalPowerInput(
        water_inlet_temp=30.0, water_outlet_temp=35.0, water_flow=1.0
    )
    assert calculate_thermal_power_heating(data) == pytest.approx(5.8125, rel=1e-3)

    data = ThermalPowerInput(
        water_inlet_temp=12.0, water_outlet_temp=7.0, water_flow=1.0
    )
    assert calculate_thermal_power_heating(data) == 0.0


def test_calculate_thermal_power_cooling():
    """Test cooling specific power calculation."""
    # Cooling: outlet < inlet
    data = ThermalPowerInput(
        water_inlet_temp=12.0, water_outlet_temp=7.0, water_flow=1.0
    )
    assert calculate_thermal_power_cooling(data) == pytest.approx(5.8125, rel=1e-3)

    # Heating: outlet > inlet -> cooling should be 0
    data = ThermalPowerInput(
        water_inlet_temp=30.0, water_outlet_temp=35.0, water_flow=1.0
    )
    assert calculate_thermal_power_cooling(data) == 0.0


class TestThermalEnergyAccumulator:
    """Tests for ThermalEnergyAccumulator logic."""

    def test_initial_state(self):
        """Test initial values of the accumulator."""
        acc = ThermalEnergyAccumulator(1.0, 10.0, 2.0, 20.0)
        assert acc.daily_heating_energy == 1.0
        assert acc.total_heating_energy == 10.0
        assert acc.daily_cooling_energy == 2.0
        assert acc.total_cooling_energy == 20.0
        assert acc.last_heating_power == 0.0
        assert acc.last_cooling_power == 0.0

    @patch("custom_components.hitachi_yutaki.domain.services.thermal.time")
    def test_heating_accumulation(self, mock_time):
        """Test heating energy accumulation."""
        acc = ThermalEnergyAccumulator()

        # Start at T=0
        mock_time.return_value = 1000.0
        acc.update(heating_power=10.0, cooling_power=0.0, compressor_running=True)

        # T=3600 (1 hour later)
        mock_time.return_value = 1000.0 + 3600.0
        acc.update(heating_power=10.0, cooling_power=0.0, compressor_running=True)

        # Energy = avg_power * hours = 10kW * 1h = 10kWh
        assert acc.daily_heating_energy == 10.0
        assert acc.total_heating_energy == 10.0
        assert acc.last_heating_power == 10.0

    @patch("custom_components.hitachi_yutaki.domain.services.thermal.time")
    def test_post_cycle_lock(self, mock_time):
        """Test the post-cycle lock logic."""
        acc = ThermalEnergyAccumulator()
        mock_time.return_value = 1000.0

        # 1. Compressor running, heating active
        acc.update(heating_power=10.0, cooling_power=0.0, compressor_running=True)
        assert acc.last_heating_power == 10.0

        # 2. Compressor stops, heating still has inertia (delta T > 0)
        acc.update(heating_power=5.0, cooling_power=0.0, compressor_running=False)
        assert acc.last_heating_power == 5.0
        assert acc._post_cycle_lock is False

        # 3. Delta T drops to 0 while compressor stopped -> lock engaged
        acc.update(heating_power=0.0, cooling_power=0.0, compressor_running=False)
        assert acc._post_cycle_lock is True
        assert acc.last_heating_power == 0.0

        # 4. Delta T goes back up (noise or pump restart) but compressor still stopped -> stay locked
        acc.update(heating_power=2.0, cooling_power=0.0, compressor_running=False)
        assert acc._post_cycle_lock is True
        assert acc.last_heating_power == 0.0  # Power forced to 0

        # 5. Compressor restarts -> lock released
        acc.update(heating_power=2.0, cooling_power=0.0, compressor_running=True)
        assert acc._post_cycle_lock is False
        assert acc.last_heating_power == 2.0

    @patch("custom_components.hitachi_yutaki.domain.services.thermal.time")
    def test_defrost_handling(self, mock_time):
        """Test handling of defrost mode."""
        acc = ThermalEnergyAccumulator()
        mock_time.return_value = 1000.0
        acc.update(heating_power=10.0, cooling_power=0.0, compressor_running=True)

        # Defrost starts
        mock_time.return_value = 1000.0 + 600.0  # 10 min
        acc.update(
            heating_power=0.0,
            cooling_power=0.0,
            compressor_running=True,
            is_defrosting=True,
        )

        # Accumulation should have happened for the previous period (0.0 power used during defrost interval)
        # Avg power = (10 + 0) / 2 = 5kW
        # Time = 1/6 h
        # Energy = 5 * 1/6 = 0.833 kWh
        assert acc.daily_heating_energy == pytest.approx(0.833, rel=1e-2)
        assert acc.last_heating_power == 0.0


class TestThermalPowerService:
    """Tests for ThermalPowerService integration."""

    def test_update_delegation(self):
        """Test that ThermalPowerService delegates to accumulator."""
        acc = ThermalEnergyAccumulator()
        service = ThermalPowerService(acc)

        # Test basic update delegation
        # heating: outlet (35) > inlet (30)
        service.update(
            water_inlet_temp=30.0,
            water_outlet_temp=35.0,
            water_flow=1.0,
            compressor_frequency=20.0,
        )

        # Expected heating power is ~5.81 kW
        assert service.get_heating_power() == pytest.approx(5.81, abs=0.01)
        assert service.get_cooling_power() == 0.0

    def test_update_invalid_data(self):
        """Test update with None values."""
        acc = ThermalEnergyAccumulator()
        service = ThermalPowerService(acc)

        # First successful update to set some state
        service.update(30.0, 35.0, 1.0, 20.0)

        # Update with None values
        service.update(None, 35.0, 1.0, 20.0)
        assert service.get_heating_power() == 0.0

    def test_getters_rounding(self):
        """Test that getters return rounded values."""
        acc = ThermalEnergyAccumulator()
        service = ThermalPowerService(acc)

        # Simulate an accumulation that results in many decimals
        # Force a value in the accumulator
        acc._daily_heating_energy = 1.234567
        assert service.get_daily_heating_energy() == 1.23
