"""Provider port interfaces for data access."""

from typing import Protocol


class DataProvider(Protocol):
    """Protocol for accessing heat pump data."""

    def get_water_inlet_temp(self) -> float | None:
        """Get water inlet temperature in °C."""

    def get_water_outlet_temp(self) -> float | None:
        """Get water outlet temperature in °C."""

    def get_water_flow(self) -> float | None:
        """Get water flow rate in m³/h."""

    def get_compressor_current(self) -> float | None:
        """Get primary compressor current in Amperes."""

    def get_compressor_frequency(self) -> float | None:
        """Get primary compressor frequency in Hz."""

    def get_secondary_compressor_current(self) -> float | None:
        """Get secondary compressor current in Amperes."""

    def get_secondary_compressor_frequency(self) -> float | None:
        """Get secondary compressor frequency in Hz."""


class StateProvider(Protocol):
    """Protocol for accessing Home Assistant entity states."""

    def get_float_from_entity(self, config_key: str) -> float | None:
        """Get float value from a configured entity.

        Args:
            config_key: Configuration key for the entity

        Returns:
            Float value or None if unavailable

        """
