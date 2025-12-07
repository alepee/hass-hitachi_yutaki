"""Thermal power calculator adapter for domain services."""

from __future__ import annotations

from ...domain.models.thermal import ThermalPowerInput
from ...domain.ports.calculators import ThermalPowerCalculator
from ...domain.services.thermal import (
    calculate_thermal_power,
    calculate_thermal_power_cooling,
    calculate_thermal_power_heating,
)


def thermal_power_calculator_wrapper(inlet: float, outlet: float, flow: float) -> float:
    """Calculate thermal power from inlet, outlet and flow parameters.

    This wrapper adapts calculate_thermal_power to match the Callable signature
    expected by COPSensor: (float, float, float) -> float

    Args:
        inlet: Water inlet temperature in °C
        outlet: Water outlet temperature in °C
        flow: Water flow rate in m³/h

    Returns:
        Thermal power in kW (absolute value)

    """
    return abs(calculate_thermal_power(ThermalPowerInput(inlet, outlet, flow)))


def thermal_power_calculator_heating_wrapper(
    inlet: float, outlet: float, flow: float
) -> float:
    """Calculate thermal power for heating mode.

    Returns positive power only when outlet > inlet (heating).
    Returns 0 when in cooling mode.

    Args:
        inlet: Water inlet temperature in °C
        outlet: Water outlet temperature in °C
        flow: Water flow rate in m³/h

    Returns:
        Thermal power in kW (0 if cooling mode)

    """
    return calculate_thermal_power_heating(ThermalPowerInput(inlet, outlet, flow))


def thermal_power_calculator_cooling_wrapper(
    inlet: float, outlet: float, flow: float
) -> float:
    """Calculate thermal power for cooling mode.

    Returns positive power only when outlet < inlet (cooling).
    Returns 0 when in heating mode.

    Args:
        inlet: Water inlet temperature in °C
        outlet: Water outlet temperature in °C
        flow: Water flow rate in m³/h

    Returns:
        Thermal power in kW (0 if heating mode)

    """
    return calculate_thermal_power_cooling(ThermalPowerInput(inlet, outlet, flow))


# Type alias for protocol compliance
ThermalPowerCalculatorImpl: type[ThermalPowerCalculator] = (
    thermal_power_calculator_wrapper
)
