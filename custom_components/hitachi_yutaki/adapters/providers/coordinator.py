"""Coordinator data provider adapter."""

from __future__ import annotations

from ...domain.ports.providers import DataProvider


class CoordinatorDataProvider:
    """Adapter to provide data from HitachiYutakiDataCoordinator."""

    def __init__(self, coordinator) -> None:
        """Initialize the provider.

        Args:
            coordinator: HitachiYutakiDataCoordinator instance

        """
        self._coordinator = coordinator

    def get_water_inlet_temp(self) -> float | None:
        """Get water inlet temperature in °C."""
        return (
            self._coordinator.data.get("water_inlet_temp")
            if self._coordinator.data
            else None
        )

    def get_water_outlet_temp(self) -> float | None:
        """Get water outlet temperature in °C."""
        return (
            self._coordinator.data.get("water_outlet_temp")
            if self._coordinator.data
            else None
        )

    def get_water_flow(self) -> float | None:
        """Get water flow rate in m³/h."""
        return (
            self._coordinator.data.get("water_flow") if self._coordinator.data else None
        )

    def get_compressor_current(self) -> float | None:
        """Get primary compressor current in Amperes."""
        return (
            self._coordinator.data.get("compressor_current")
            if self._coordinator.data
            else None
        )

    def get_compressor_frequency(self) -> float | None:
        """Get primary compressor frequency in Hz."""
        return (
            self._coordinator.data.get("compressor_frequency")
            if self._coordinator.data
            else None
        )

    def get_secondary_compressor_current(self) -> float | None:
        """Get secondary compressor current in Amperes."""
        return (
            self._coordinator.data.get("secondary_compressor_current")
            if self._coordinator.data
            else None
        )

    def get_secondary_compressor_frequency(self) -> float | None:
        """Get secondary compressor frequency in Hz."""
        return (
            self._coordinator.data.get("secondary_compressor_frequency")
            if self._coordinator.data
            else None
        )


# Type alias for protocol compliance
DataProviderImpl: type[DataProvider] = CoordinatorDataProvider
