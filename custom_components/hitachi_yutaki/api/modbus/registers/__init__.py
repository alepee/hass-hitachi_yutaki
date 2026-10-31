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
    """A written value the hardware forgets on reboot, put back by the client.

    The restore is mechanical: the client never interprets the value. A
    reading of 0, or outside ``valid_range``, is a lost value, written back
    to its reference (the last value written, or the last reading that was
    not lost) once a successful read has seen it lost.

    ``while_on`` names a kept value this one depends on (e.g. an enable
    flag): it is only written back while that value reads non-zero, or is
    being written back too, and that value is only written back once all of
    its dependents read right and are confirmed. A CONTROL-only register
    reads back what was written, so only its dependents, read from STATUS
    registers, prove the unit applied anything: that is why it goes last.

    ``seed_from`` names another kept value to copy instead of a reference
    (e.g. a room value seeded with the target, which keeps the unit idle
    until the real one is written). It is written right after its source,
    from the value just written back.
    """

    valid_range: tuple[float, float] | None = None
    while_on: str | None = None
    seed_from: str | None = None


def validate_kept_registers(registers: dict[str, "RegisterDefinition"]) -> None:
    """Check the ``Keep`` declarations of a register map, raising ValueError.

    ``while_on`` and ``seed_from`` must name another kept register; a ``while_on`` target depends on nothing, and a ``seed_from``
    source shares the same ``while_on`` and is not seeded itself. That keeps
    the restore order a fixed three steps, with no cycle.
    """
    for key, definition in registers.items():
        keep = definition.keep
        if keep is None:
            continue
        for name, ref in (("while_on", keep.while_on), ("seed_from", keep.seed_from)):
            if ref is None:
                continue
            target = registers.get(ref)
            if ref == key or target is None or target.keep is None:
                raise ValueError(f"{key}: {name} must name another kept register")
        if keep.while_on is not None:
            gate = registers[keep.while_on].keep
            if gate.while_on is not None or gate.seed_from is not None:
                raise ValueError(f"{key}: while_on target must depend on nothing")
        if keep.seed_from is not None:
            source = registers[keep.seed_from].keep
            if source.seed_from is not None or source.while_on != keep.while_on:
                raise ValueError(f"{key}: seed_from source must share while_on")


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
            writes it back mechanically (see :class:`Keep`). Needs a
            ``serializer`` when the deserialized value is not the raw one.

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
