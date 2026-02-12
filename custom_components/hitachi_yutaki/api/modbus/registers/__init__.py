"""Register map for Hitachi heat pumps."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class RegisterDefinition:
    """Class to define a register.

    Attributes:
        address: Read address (STATUS register for gateways with separate R/W ranges).
        deserializer: Optional function to convert raw register value on read.
        serializer: Optional function to convert value before writing.
        write_address: Write address if different from read address (e.g. HC-A(16/64)MB).
            When None, writes use the same address as reads.

    """

    address: int
    deserializer: Callable[[Any], Any] | None = None
    serializer: Callable[[Any], Any] | None = None
    write_address: int | None = None


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

    @property
    @abstractmethod
    def all_registers(self) -> dict[str, RegisterDefinition]:
        """Return all registers in a single map for easy lookup."""

    @property
    @abstractmethod
    def writable_keys(self) -> set[str]:
        """Return the set of register keys that can be written to."""

    @property
    @abstractmethod
    def system_state_issues(self) -> dict[int, str]:
        """Return mapping of system state values to issue keys."""

    # System configuration bit masks

    @property
    @abstractmethod
    def masks_circuit(self) -> dict:
        """Return circuit configuration bit masks."""

    @property
    @abstractmethod
    def mask_dhw(self) -> int:
        """Return DHW configuration bit mask."""

    @property
    @abstractmethod
    def mask_pool(self) -> int:
        """Return pool configuration bit mask."""

    # System status bit masks

    @property
    @abstractmethod
    def mask_defrost(self) -> int:
        """Return defrost status bit mask."""

    @property
    @abstractmethod
    def mask_solar(self) -> int:
        """Return solar status bit mask."""

    @property
    @abstractmethod
    def mask_pump1(self) -> int:
        """Return pump 1 status bit mask."""

    @property
    @abstractmethod
    def mask_pump2(self) -> int:
        """Return pump 2 status bit mask."""

    @property
    @abstractmethod
    def mask_pump3(self) -> int:
        """Return pump 3 status bit mask."""

    @property
    @abstractmethod
    def mask_compressor(self) -> int:
        """Return compressor status bit mask."""

    @property
    @abstractmethod
    def mask_boiler(self) -> int:
        """Return boiler status bit mask."""

    @property
    @abstractmethod
    def mask_dhw_heater(self) -> int:
        """Return DHW heater status bit mask."""

    @property
    @abstractmethod
    def mask_space_heater(self) -> int:
        """Return space heater status bit mask."""

    @property
    @abstractmethod
    def mask_smart_function(self) -> int:
        """Return smart function status bit mask."""

    # HVAC unit mode constants

    @property
    @abstractmethod
    def hvac_unit_mode_cool(self) -> int:
        """Return the raw value for cooling mode."""

    @property
    @abstractmethod
    def hvac_unit_mode_heat(self) -> int:
        """Return the raw value for heating mode."""

    @property
    @abstractmethod
    def hvac_unit_mode_auto(self) -> int | None:
        """Return the raw value for auto mode, or None if not supported."""

    @abstractmethod
    def serialize_otc_method(self, value: str) -> int:
        """Convert a heating OTC method constant to a raw register value."""

    @abstractmethod
    def serialize_otc_method_cooling(self, value: str) -> int:
        """Convert a cooling OTC method constant to a raw register value."""
