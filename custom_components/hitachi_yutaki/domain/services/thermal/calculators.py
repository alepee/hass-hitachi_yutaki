"""Thermal power calculation functions.

Pure business logic isolated from infrastructure concerns.
"""

from __future__ import annotations

from ...models.thermal import ThermalPowerInput
from .constants import WATER_FLOW_TO_KGS, WATER_SPECIFIC_HEAT


def calculate_thermal_power(data: ThermalPowerInput) -> float:
    """Calculate signed thermal power in kW from input data.

    Positive values indicate heating (outlet > inlet).
    Negative values indicate cooling (outlet < inlet).

    Args:
        data: Input data containing temperatures and flow

    Returns:
        Signed thermal power in kW

    """
    water_flow_kgs = data.water_flow * WATER_FLOW_TO_KGS
    delta_t = data.water_outlet_temp - data.water_inlet_temp

    thermal_power = water_flow_kgs * WATER_SPECIFIC_HEAT * delta_t
    return thermal_power


def calculate_thermal_power_heating(data: ThermalPowerInput) -> float:
    """Calculate thermal power for heating mode.

    Returns positive power only when outlet > inlet (heating).
    Returns 0 when in cooling mode or invalid conditions.

    Args:
        data: Input data containing temperatures and flow

    Returns:
        Thermal power in kW (0 if cooling mode)

    """
    thermal_power = calculate_thermal_power(data)
    return max(0.0, thermal_power)


def calculate_thermal_power_cooling(data: ThermalPowerInput) -> float:
    """Calculate thermal power for cooling mode.

    Returns positive power only when outlet < inlet (cooling).
    Returns 0 when in heating mode or invalid conditions.

    Args:
        data: Input data containing temperatures and flow

    Returns:
        Thermal power in kW (0 if heating mode)

    """
    thermal_power = calculate_thermal_power(data)
    return max(0.0, -thermal_power)
