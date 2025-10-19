"""Calculator port interfaces."""

from abc import ABC, abstractmethod
from typing import Protocol


class ThermalPowerCalculator(Protocol):
    """Protocol for thermal power calculation."""

    def __call__(self, inlet: float, outlet: float, flow: float) -> float:
        """Calculate thermal power from temperature and flow.

        Args:
            inlet: Inlet temperature in °C
            outlet: Outlet temperature in °C
            flow: Water flow in m³/h

        Returns:
            Thermal power in kW

        """
        ...


class ElectricalPowerCalculator(Protocol):
    """Protocol for electrical power calculation."""

    def __call__(self, current: float) -> float:
        """Calculate electrical power from current and optional voltage.

        Args:
            current: Electrical current in Amperes

        Returns:
            Electrical power in kW

        """
        ...
