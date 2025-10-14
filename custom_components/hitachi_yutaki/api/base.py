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

    @property
    @abstractmethod
    def is_defrosting(self) -> bool:
        """Return True if the unit is in defrost mode."""

    @property
    @abstractmethod
    def is_solar_active(self) -> bool:
        """Return True if solar system is active."""

    @property
    @abstractmethod
    def is_pump1_running(self) -> bool:
        """Return True if pump 1 is running."""

    @property
    @abstractmethod
    def is_pump2_running(self) -> bool:
        """Return True if pump 2 is running."""

    @property
    @abstractmethod
    def is_pump3_running(self) -> bool:
        """Return True if pump 3 is running."""

    @property
    @abstractmethod
    def is_compressor_running(self) -> bool:
        """Return True if compressor is running."""

    @property
    @abstractmethod
    def is_boiler_active(self) -> bool:
        """Return True if backup boiler is active."""

    @property
    @abstractmethod
    def is_dhw_heater_active(self) -> bool:
        """Return True if DHW electric heater is active."""

    @property
    @abstractmethod
    def is_space_heater_active(self) -> bool:
        """Return True if space heating electric heater is active."""

    @property
    @abstractmethod
    def is_smart_function_active(self) -> bool:
        """Return True if smart grid function is active."""
