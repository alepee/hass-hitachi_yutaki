"""Storage abstractions for Hitachi Yutaki services."""

from .in_memory import InMemoryStorage
from .interface import AbstractStorage

__all__ = ["AbstractStorage", "InMemoryStorage"]
