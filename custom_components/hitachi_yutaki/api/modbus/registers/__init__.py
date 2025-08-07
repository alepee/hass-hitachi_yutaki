"""Register map interfaces for Modbus adapters.

This layer is Modbus-specific and translates logical keys to register addresses.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Container


class HitachiRegisterMap(ABC):
    """Abstract register map for a Modbus gateway/model.

    Implementations provide a mapping from logical keys (e.g., "water_flow")
    to Modbus holding register addresses.
    """

    # ---- Address resolution ----
    @abstractmethod
    def address_for_key(self, key: str) -> int:
        """Return the holding register address for a logical key.

        Should raise KeyError if the key is unknown for this map.
        """

    def has_key(self, key: str) -> bool:
        try:
            self.address_for_key(key)
            return True
        except KeyError:
            return False

    @abstractmethod
    def keys(self) -> Iterable[str]:
        """Return all known logical keys for this map."""

    # ---- Groupings (used by application layer) ----
    @abstractmethod
    def control_keys(self) -> Container[str]:
        """Keys that are writable and control behavior."""

    @abstractmethod
    def sensor_keys(self) -> Container[str]:
        """Keys that represent sensor/telemetry values."""

    @abstractmethod
    def r134a_keys(self) -> Container[str]:
        """Keys specific to S80 R134a secondary loop."""

    @abstractmethod
    def config_keys(self) -> Container[str]:
        """Keys for basic configuration/status used broadly (unit_model, system_config, system_status, system_state, central_control_mode)."""

