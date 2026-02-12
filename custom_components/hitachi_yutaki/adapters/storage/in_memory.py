"""In-memory storage implementation for domain services."""

from __future__ import annotations

from collections import deque
from typing import TypeVar

from ...domain.ports.storage import Storage

T = TypeVar("T")


class InMemoryStorage(Storage[T]):
    """In-memory storage implementation using a deque."""

    def __init__(self, max_len: int | None = None) -> None:
        """Initialize the in-memory storage.

        Args:
            max_len: Maximum number of items to store (None for unlimited)

        """
        self._data: deque[T] = deque(maxlen=max_len)

    def append(self, item: T) -> None:
        """Add an item to the storage.

        Args:
            item: Item to add

        """
        self._data.append(item)

    def popleft(self) -> T:
        """Remove and return an item from the left side of the storage.

        Returns:
            The leftmost item

        Raises:
            IndexError: If storage is empty

        """
        return self._data.popleft()

    def get_all(self) -> list[T]:
        """Return all items in the storage.

        Returns:
            List of all items

        """
        return list(self._data)

    def __len__(self) -> int:
        """Return the number of items in the storage.

        Returns:
            Number of items

        """
        return len(self._data)
