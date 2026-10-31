"""Register map for Hitachi heat pumps."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Readings the indoor unit relays from the outdoor unit. Tg, Ti and EVI are
# measured on the indoor side of a split unit, so they are not listed.
OUTDOOR_UNIT_KEYS = (
    "outdoor_temp",
    "compressor_td_discharge_temp",
    "compressor_te_evaporator_temp",
    "compressor_evo_outdoor_expansion_valve_opening",
    "compressor_frequency",
    "compressor_current",
)

# Alarm 03: abnormal transmission between the indoor and the outdoor unit.
OUTDOOR_LINK_ALARMS = frozenset({"alarm_code_3"})


@dataclass(frozen=True)
class Keep:
    """A written value the hardware forgets on reboot, written back by the client.

    A reading of 0 or outside ``valid_range`` is a lost value. ``while_on``
    names a kept flag: the value is only written back while that flag reads
    on, or is written back in the same poll.
    """

    valid_range: tuple[float, float] | None = None
    while_on: str | None = None


@dataclass
class RegisterDefinition:
    """Class to define a register.

    Attributes:
        address: Read address (STATUS register for gateways with separate R/W ranges).
        deserializer: Optional function to convert raw register value on read.
        serializer: Optional function to convert value before writing.
        write_address: Write address if different from read address (e.g. HC-A(16/64)MB).
            When None, writes use the same address as reads.
        fallback: Optional fallback register to read when the primary returns None
            (e.g. 0xFFFF sensor error) or a read error.
        sentinel_values: Set of deserialized values that indicate the sensor is
            unavailable. These are gateway-specific conventions (e.g. -127 for
            absent sensor, -67 for unavailable module). When a read returns one
            of these values, the gateway returns None instead.
        keep: Set when the hardware forgets the value on reboot: the client
            writes the last known value back (see :class:`Keep`).

    """

    address: int
    deserializer: Callable[[Any], Any] | None = None
    serializer: Callable[[Any], Any] | None = None
    write_address: int | None = None
    fallback: "RegisterDefinition | None" = None
    sentinel_values: frozenset[int] | None = None
    keep: Keep | None = None


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
    def outdoor_unit_keys(self) -> list[str]:
        """Return the keys whose value the indoor unit relays from the outdoor unit."""
        return [key for key in OUTDOOR_UNIT_KEYS if key in self.all_registers]

    @property
    def outdoor_link_alarms(self) -> frozenset[str]:
        """Return the alarm codes meaning the outdoor unit is unreachable."""
        return OUTDOOR_LINK_ALARMS

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
    def masks_circuit_thermostat(self) -> dict[int, int]:
        """Return per-circuit "room thermostat available" bit masks.

        Reported by the unit for the Hitachi thermostats bound to it; a
        third-party thermostat on the demand input is not reported.
        """

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
    def serialize_otc_method_heating(self, value: str) -> int:
        """Convert a heating OTC method constant to a raw register value."""

    @abstractmethod
    def serialize_otc_method_cooling(self, value: str) -> int:
        """Convert a cooling OTC method constant to a raw register value."""


# Import concrete register map classes for variant lookup
from .atw_mbs_02 import AtwMbs02RegisterMap  # noqa: E402
from .atw_mbs_02_pre2016 import AtwMbs02Pre2016RegisterMap  # noqa: E402

GATEWAY_VARIANTS: dict[str, dict[str, type[HitachiRegisterMap]]] = {
    "modbus_atw_mbs_02": {
        "gen1": AtwMbs02Pre2016RegisterMap,
        "gen2": AtwMbs02RegisterMap,
    },
}
