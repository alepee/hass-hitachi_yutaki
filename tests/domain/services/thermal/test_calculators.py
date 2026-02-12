"""Tests for thermal power calculation functions."""

import pytest

from custom_components.hitachi_yutaki.domain.models.thermal import ThermalPowerInput
from custom_components.hitachi_yutaki.domain.services.thermal.calculators import (
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
