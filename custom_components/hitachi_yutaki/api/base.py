"""Base classes for Hitachi API."""

from abc import ABC, abstractmethod
from typing import Any


class HitachiApiClient(ABC):
    """Abstract class for a Hitachi API client."""

    @property
    @abstractmethod
    def register_map(self) -> Any:
        """Return the register map for the gateway."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the API."""

    @abstractmethod
    async def close(self) -> bool:
        """Close the connection to the API."""

    @property
    @abstractmethod
    def connected(self) -> bool:
        """Return True if the client is connected to the API."""

    @property
    @abstractmethod
    def capabilities(self) -> dict:
        """Return the capabilities of the gateway."""

    @abstractmethod
    async def get_model_key(self) -> str:
        """Return the model of the heat pump."""

    @abstractmethod
    async def read_value(self, key: str) -> int | None:
        """Read a value from the API."""

    @abstractmethod
    async def write_value(self, key: str, value: int) -> bool:
        """Write a value to the API."""

    @abstractmethod
    async def read_values(self, keys_to_read: list[str]) -> None:
        """Fetch data from the heat pump for the given keys."""

    @property
    @abstractmethod
    def has_dhw(self) -> bool:
        """Return True if DHW is configured."""

    @property
    @abstractmethod
    def has_circuit1_heating(self) -> bool:
        """Return True if heating for circuit 1 is configured."""

    @property
    @abstractmethod
    def has_circuit1_cooling(self) -> bool:
        """Return True if cooling for circuit 1 is configured."""

    @property
    @abstractmethod
    def has_circuit2_heating(self) -> bool:
        """Return True if heating for circuit 2 is configured."""

    @property
    @abstractmethod
    def has_circuit2_cooling(self) -> bool:
        """Return True if cooling for circuit 2 is configured."""

    @property
    @abstractmethod
    def has_pool(self) -> bool:
        """Return True if pool heating is configured."""

    @abstractmethod
    def decode_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """Decode raw config data into a dictionary of boolean flags."""
