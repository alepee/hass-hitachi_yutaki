"""Adapters for sensor calculations.

This module provides backward compatibility by re-exporting adapters from the new location.
"""

from __future__ import annotations

# Re-export from new adapters location for backward compatibility
from ..adapters.calculators.electrical import ElectricalPowerCalculatorAdapter
from ..adapters.calculators.thermal import (
    thermal_power_calculator_wrapper as _calculate_thermal_power_wrapper,
)
