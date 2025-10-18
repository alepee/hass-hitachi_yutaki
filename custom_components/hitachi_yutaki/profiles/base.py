"""Base profile for Hitachi heat pumps."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class HitachiHeatPumpProfile(ABC):
    """Abstract base class for a Hitachi Heat Pump profile.

    A profile defines the capabilities of a specific heat pump model,
    such as its support for Domestic Hot Water (DHW), swimming pools,
    or multiple heating circuits. It can also specify model-specific
    entity overrides or extra register keys required for its operation.
    """

    @staticmethod
    @abstractmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""

    @property
    def supports_dhw(self) -> bool:
        """Return True if the heat pump supports Domestic Hot Water."""
        return True

    @property
    def supports_pool(self) -> bool:
        """Return True if the heat pump supports pool heating."""
        return False

    @property
    def supports_circuit1(self) -> bool:
        """Return True if the heat pump supports heating circuit 1."""
        return True

    @property
    def supports_circuit2(self) -> bool:
        """Return True if the heat pump supports heating circuit 2."""
        return True

    @property
    def supports_secondary_compressor(self) -> bool:
        """Return True if the heat pump has a secondary compressor."""
        return False

    @property
    def supports_boiler(self) -> bool:
        """Return True if the heat pump has a backup boiler."""
        return True

    @property
    def extra_register_keys(self) -> list[str]:
        """Return the extra register keys for the profile."""
        return []

    @property
    def entity_overrides(self) -> dict:
        """Return a dictionary of entity overrides for the profile.

        This allows a profile to modify the behavior or parameters of
        specific entities, such as changing temperature limits for a
        water heater or altering the logic for a binary sensor.
        """
        return {}
