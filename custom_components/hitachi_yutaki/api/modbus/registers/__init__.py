"""Register map for Hitachi heat pumps."""

from abc import ABC, abstractmethod


class HitachiRegisterMap(ABC):
    """Abstract class for a Hitachi register map."""

    @property
    @abstractmethod
    def gateway_keys(self) -> list[str]:
        """Return the list of gateway keys."""

    @property
    @abstractmethod
    def control_unit_keys(self) -> list[str]:
        """Return the list of control unit keys."""

    @property
    @abstractmethod
    def primary_compressor_keys(self) -> list[str]:
        """Return the list of primary compressor keys."""

    @property
    @abstractmethod
    def secondary_compressor_keys(self) -> list[str]:
        """Return the list of secondary compressor keys."""

    @property
    @abstractmethod
    def circuit_1_keys(self) -> list[str]:
        """Return the list of circuit 1 keys."""

    @property
    @abstractmethod
    def circuit_2_keys(self) -> list[str]:
        """Return the list of circuit 2 keys."""

    @property
    @abstractmethod
    def dhw_keys(self) -> list[str]:
        """Return the list of DHW keys."""

    @property
    @abstractmethod
    def pool_keys(self) -> list[str]:
        """Return the list of pool keys."""

    @property
    def base_keys(self) -> list[str]:
        """Return the list of all base keys, excluding model-specific ones."""
        return (
            self.gateway_keys
            + self.control_unit_keys
            + self.primary_compressor_keys
            + self.circuit_1_keys
            + self.circuit_2_keys
            + self.dhw_keys
            + self.pool_keys
        )
