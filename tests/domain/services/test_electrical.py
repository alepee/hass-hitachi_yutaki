"""Tests for electrical power calculation service."""

from custom_components.hitachi_yutaki.domain.models.electrical import (
    ElectricalPowerInput,
)
from custom_components.hitachi_yutaki.domain.services.electrical import (
    POWER_FACTOR,
    THREE_PHASE_FACTOR,
    VOLTAGE_SINGLE_PHASE,
    VOLTAGE_THREE_PHASE,
    calculate_electrical_power,
)


def test_measured_power_used_directly():
    """Measured power (already in kW from adapter) is returned as-is."""
    data = ElectricalPowerInput(current=10.0, measured_power=2.5)
    assert calculate_electrical_power(data) == 2.5


def test_measured_power_small_value_not_divided():
    """Small measured_power values are no longer divided by 1000.

    Regression test for issue #182: a heat pump in standby consuming 0.03 kW
    must NOT be treated as 30 kW.
    """
    data = ElectricalPowerInput(current=10.0, measured_power=0.03)
    assert calculate_electrical_power(data) == 0.03


def test_fallback_to_voltage_current_single_phase():
    """Without measured_power, single-phase P = U * I * cos(phi) / 1000."""
    data = ElectricalPowerInput(
        current=10.0, voltage=230.0, is_three_phase=False
    )
    expected = (230.0 * 10.0 * POWER_FACTOR) / 1000
    assert calculate_electrical_power(data) == expected


def test_fallback_to_voltage_current_three_phase():
    """Without measured_power, three-phase P = U * I * cos(phi) * sqrt(3) / 1000."""
    data = ElectricalPowerInput(
        current=10.0, voltage=400.0, is_three_phase=True
    )
    expected = (400.0 * 10.0 * POWER_FACTOR * THREE_PHASE_FACTOR) / 1000
    assert calculate_electrical_power(data) == expected


def test_fallback_to_default_voltage_single_phase():
    """Without voltage, default single-phase voltage (230V) is used."""
    data = ElectricalPowerInput(current=10.0, is_three_phase=False)
    expected = (VOLTAGE_SINGLE_PHASE * 10.0 * POWER_FACTOR) / 1000
    assert calculate_electrical_power(data) == expected


def test_fallback_to_default_voltage_three_phase():
    """Without voltage, default three-phase voltage (400V) is used."""
    data = ElectricalPowerInput(current=10.0, is_three_phase=True)
    expected = (VOLTAGE_THREE_PHASE * 10.0 * POWER_FACTOR * THREE_PHASE_FACTOR) / 1000
    assert calculate_electrical_power(data) == expected


def test_measured_power_zero():
    """Zero measured power is returned as-is (not treated as None)."""
    data = ElectricalPowerInput(current=10.0, measured_power=0.0)
    assert calculate_electrical_power(data) == 0.0
