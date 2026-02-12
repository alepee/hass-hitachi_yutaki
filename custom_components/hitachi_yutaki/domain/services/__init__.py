"""Domain services for Hitachi Yutaki."""

from .cop import COPService, EnergyAccumulator
from .thermal import ThermalEnergyAccumulator, ThermalPowerService
from .timing import CompressorHistory, CompressorTimingService

# Configuration constants
COP_MEASUREMENTS_HISTORY_SIZE = 100
COP_MEASUREMENTS_INTERVAL = 60  # seconds
COP_MEASUREMENTS_PERIOD_MINUTES = 30
COP_MIN_MEASUREMENTS = 5
COP_MIN_TIME_SPAN = 5  # minutes
COP_OPTIMAL_MEASUREMENTS = 15
COP_OPTIMAL_TIME_SPAN = 15  # minutes

__all__ = [
    "COPService",
    "EnergyAccumulator",
    "ThermalEnergyAccumulator",
    "ThermalPowerService",
    "CompressorHistory",
    "CompressorTimingService",
    "COP_MEASUREMENTS_HISTORY_SIZE",
    "COP_MEASUREMENTS_INTERVAL",
    "COP_MEASUREMENTS_PERIOD_MINUTES",
    "COP_MIN_MEASUREMENTS",
    "COP_MIN_TIME_SPAN",
    "COP_OPTIMAL_MEASUREMENTS",
    "COP_OPTIMAL_TIME_SPAN",
]
