"""In-memory storage implementation."""

from collections import deque
from typing import TypeVar

from .interface import AbstractStorage

T = TypeVar("T")


class InMemoryStorage(AbstractStorage[T]):
    """In-memory storage implementation using a deque."""

    def __init__(self, max_len: int | None = None) -> None:
        """Initialize the in-memory storage."""
        self._data: deque[T] = deque(maxlen=max_len)

    def append(self, item: T) -> None:
        """Add an item to the storage."""
        self._data.append(item)

    def popleft(self) -> T:
        """Remove and return an item from the left side of the storage."""
        return self._data.popleft()

    def get_all(self) -> list[T]:
        """Return all items in the storage."""
        return list(self._data)

    def __len__(self) -> int:
        """Return the number of items in the storage."""
        return len(self._data)
