"""Storage abstractions for Hitachi Yutaki services."""

from abc import ABC, abstractmethod
from typing import TypeVar

from .in_memory import InMemoryStorage

T = TypeVar("T")


class AbstractStorage[T](ABC):
    """Abstract interface for a data storage."""

    @abstractmethod
    def append(self, item: T) -> None:
        """Add an item to the storage."""

    @abstractmethod
    def popleft(self) -> T:
        """Remove and return an item from the left side of the storage."""

    @abstractmethod
    def get_all(self) -> list[T]:
        """Return all items in the storage."""

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of items in the storage."""


__all__ = ["AbstractStorage", "InMemoryStorage"]
