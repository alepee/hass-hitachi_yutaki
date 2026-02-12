"""Storage port interface."""

from abc import ABC, abstractmethod
from typing import TypeVar

T = TypeVar("T")


class Storage[T](ABC):
    """Abstract interface for data storage."""

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
