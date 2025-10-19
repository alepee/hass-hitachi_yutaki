"""Thermal power calculator adapter for domain services."""

from __future__ import annotations

from ...domain.models.thermal import ThermalPowerInput
from ...domain.ports.calculators import ThermalPowerCalculator
from ...domain.services.thermal import calculate_thermal_power


def thermal_power_calculator_wrapper(inlet: float, outlet: float, flow: float) -> float:
    """Calculate thermal power from inlet, outlet and flow parameters.

    This wrapper adapts calculate_thermal_power to match the Callable signature
    expected by COPSensor: (float, float, float) -> float

    Args:
        inlet: Water inlet temperature in °C
        outlet: Water outlet temperature in °C
        flow: Water flow rate in m³/h

    Returns:
        Thermal power in kW

    """
    return calculate_thermal_power(ThermalPowerInput(inlet, outlet, flow))


# Type alias for protocol compliance
ThermalPowerCalculatorImpl: type[ThermalPowerCalculator] = (
    thermal_power_calculator_wrapper
)
