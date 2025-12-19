"""Tests for electrical power calculation service."""

import pytest

from custom_components.hitachi_yutaki.domain.models.electrical import ElectricalPowerInput
from custom_components.hitachi_yutaki.domain.services.electrical import (
    POWER_FACTOR,
    THREE_PHASE_FACTOR,
    VOLTAGE_SINGLE_PHASE,
    VOLTAGE_THREE_PHASE,
    calculate_electrical_power,
)


def test_calculate_electrical_power_measured_kw():
    """Test when measured power is provided in kW."""
    # Below 50, use as is
    data = ElectricalPowerInput(current=0.0, measured_power=12.5)
    assert calculate_electrical_power(data) == 12.5

    data = ElectricalPowerInput(current=0.0, measured_power=50.0)
    assert calculate_electrical_power(data) == 50.0


def test_calculate_electrical_power_measured_w():
    """Test when measured power is provided in Watts."""
    # Above 50, divide by 1000
    data = ElectricalPowerInput(current=0.0, measured_power=2500.0)
    assert calculate_electrical_power(data) == 2.5

    data = ElectricalPowerInput(current=0.0, measured_power=50.1)
    assert calculate_electrical_power(data) == pytest.approx(0.0501)


def test_calculate_electrical_power_single_phase_default():
    """Test single phase calculation with default voltage."""
    # P = U * I * cos phi / 1000
    # P = 230 * 10 * 0.9 / 1000 = 2.07 kW
    data = ElectricalPowerInput(current=10.0, is_three_phase=False)
    expected = (VOLTAGE_SINGLE_PHASE * 10.0 * POWER_FACTOR) / 1000
    assert calculate_electrical_power(data) == pytest.approx(expected)


def test_calculate_electrical_power_three_phase_default():
    """Test three phase calculation with default voltage."""
    # P = U * I * cos phi * sqrt(3) / 1000
    # P = 400 * 10 * 0.9 * 1.732 / 1000 = 6.2352 kW
    data = ElectricalPowerInput(current=10.0, is_three_phase=True)
    expected = (VOLTAGE_THREE_PHASE * 10.0 * POWER_FACTOR * THREE_PHASE_FACTOR) / 1000
    assert calculate_electrical_power(data) == pytest.approx(expected)


def test_calculate_electrical_power_single_phase_custom_voltage():
    """Test single phase calculation with custom voltage."""
    data = ElectricalPowerInput(current=10.0, voltage=220.0, is_three_phase=False)
    expected = (220.0 * 10.0 * POWER_FACTOR) / 1000
    assert calculate_electrical_power(data) == pytest.approx(expected)


def test_calculate_electrical_power_three_phase_custom_voltage():
    """Test three phase calculation with custom voltage."""
    data = ElectricalPowerInput(current=10.0, voltage=380.0, is_three_phase=True)
    expected = (380.0 * 10.0 * POWER_FACTOR * THREE_PHASE_FACTOR) / 1000
    assert calculate_electrical_power(data) == pytest.approx(expected)

