"""Electrical power calculation service.

Pure business logic isolated from infrastructure concerns.
"""

from __future__ import annotations

from ..models.electrical import ElectricalPowerInput

# Configuration constants for electrical power calculation
POWER_FACTOR = 0.9
THREE_PHASE_FACTOR = 1.732
VOLTAGE_SINGLE_PHASE = 230.0
VOLTAGE_THREE_PHASE = 400.0


def calculate_electrical_power(data: ElectricalPowerInput) -> float:
    """Calculate electrical power in kW from input data.

    Priority:
    1. Use measured_power if available (most accurate)
    2. Calculate from voltage and current
    3. Use default voltage for calculation

    Args:
        data: ElectricalPowerInput with current and optional measurements

    Returns:
        Electrical power in kW

    """
    # Priority 1: Use direct power measurement if available
    if data.measured_power is not None:
        # Simple heuristic to convert W to kW if necessary
        return (
            data.measured_power / 1000
            if data.measured_power > 50
            else data.measured_power
        )

    # Priority 2: Calculate from voltage and current
    voltage = data.voltage
    if voltage is None:
        # Use default voltage based on power supply type
        voltage = VOLTAGE_THREE_PHASE if data.is_three_phase else VOLTAGE_SINGLE_PHASE

    # Calculate power based on supply type
    if data.is_three_phase:
        # Three phase: P = U * I * cos φ * √3
        power = (voltage * data.current * POWER_FACTOR * THREE_PHASE_FACTOR) / 1000
    else:
        # Single phase: P = U * I * cos φ
        power = (voltage * data.current * POWER_FACTOR) / 1000

    return power
