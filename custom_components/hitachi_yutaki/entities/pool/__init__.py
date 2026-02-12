"""Pool domain entities."""

from .numbers import build_pool_numbers
from .sensors import build_pool_sensors
from .switches import build_pool_switches

__all__ = [
    "build_pool_sensors",
    "build_pool_numbers",
    "build_pool_switches",
]
