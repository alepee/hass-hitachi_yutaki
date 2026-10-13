"""HC-A(16/64)MB gateway unit table (#353, #476).

The gateway exposes, in input registers starting at 200, one 4-register
descriptor per slot: ``[present, Ou, Iu, slot]``.

- ``present``: 1 on an occupied slot, 0 on an empty one.
- ``Ou``: outdoor refrigerant cycle; keys the outdoor register block.
- ``Iu``: indoor unit address on the H-LINK bus.
- ``slot``: the slot index itself; also the id keying the indoor register
  block (``5000 + slot * 200``). 255 on an empty slot.

The slot is NOT a stable identity. The gateway lists the units sorted by their
H-LINK address and packs them from slot 0, so a unit missing while the bus is
enumerated shifts every unit with a higher address down by one slot. A unit is
identified by its ``(Ou, Iu)`` pair instead, and its current slot is looked up
in the table.

Pure Python, no Home Assistant or pymodbus dependency.
"""

from __future__ import annotations

from dataclasses import dataclass

UNIT_TABLE_BASE = 200
UNIT_TABLE_STRIDE = 4
# Slots read: the config flow accepts unit ids 0-15 (HC-A16MB table size).
UNIT_TABLE_SLOTS = 16
# Sentinel written by the gateway on an empty slot.
UNIT_TABLE_SENTINEL = 0xFF


@dataclass(frozen=True)
class UnitSlot:
    """One decoded slot of the gateway unit table."""

    slot: int
    present: int
    outdoor_cycle: int
    indoor_address: int
    slot_echo: int

    @property
    def is_empty(self) -> bool:
        """Return True for a properly cleared slot."""
        return self.present == 0 and self.outdoor_cycle == UNIT_TABLE_SENTINEL

    @property
    def is_valid(self) -> bool:
        """Return True for an occupied slot whose descriptor is consistent.

        A slot is trusted only when the presence flag is set, the cycle and
        address are real values, and the slot echo matches the slot index.
        Anything else is a record the gateway has not finished writing or
        clearing while it re-enumerates the bus.
        """
        return (
            self.present == 1
            and UNIT_TABLE_SENTINEL not in self.identity
            and self.slot_echo == self.slot
        )

    @property
    def identity(self) -> tuple[int, int]:
        """Return the stable ``(Ou, Iu)`` identity of the unit in this slot."""
        return (self.outdoor_cycle, self.indoor_address)


def slot_address(slot: int) -> int:
    """Return the first input register of a slot descriptor."""
    return UNIT_TABLE_BASE + slot * UNIT_TABLE_STRIDE


def parse_unit_table(registers: list[int], first_slot: int = 0) -> list[UnitSlot]:
    """Decode raw unit table registers into slots.

    Args:
        registers: Raw input registers, a whole number of 4-register slots.
        first_slot: Slot index of the first descriptor in ``registers``.

    Returns:
        One ``UnitSlot`` per complete descriptor.

    """
    return [
        UnitSlot(
            first_slot + i // UNIT_TABLE_STRIDE, *registers[i : i + UNIT_TABLE_STRIDE]
        )
        for i in range(0, len(registers) - UNIT_TABLE_STRIDE + 1, UNIT_TABLE_STRIDE)
    ]


def is_settled(table: list[UnitSlot]) -> bool:
    """Return True when every slot is either valid or properly empty."""
    return all(s.is_valid or s.is_empty for s in table)


@dataclass(frozen=True)
class SlotResolution:
    """Outcome of looking a unit up in the unit table."""

    slot: UnitSlot | None
    reason: str | None = None


# Resolution failure reasons.
REASON_NOT_SETTLED = "not_settled"
REASON_NOT_FOUND = "not_found"
REASON_AMBIGUOUS = "ambiguous"


def resolve_slot(
    table: list[UnitSlot],
    stored_slot: int,
    outdoor_cycle: int | None,
    indoor_address: int | None,
) -> SlotResolution:
    """Find the current slot of a unit from what its config entry stores.

    - ``(Ou, Iu)`` known: the slot holding that pair.
    - Only ``Ou`` known (entries created before #476): the slots on that
      cycle, preferring the stored slot when several units share the cycle.
    - Nothing known (entries created before #353): the stored slot, as before.

    Never falls back to a slot holding another unit: when the unit is not in
    the table, the caller must not read whatever now occupies its old slot.
    """
    valid = [s for s in table if s.is_valid]

    if outdoor_cycle is None:
        matches = [s for s in valid if s.slot == stored_slot]
    elif indoor_address is None:
        matches = [s for s in valid if s.outdoor_cycle == outdoor_cycle]
    else:
        matches = [s for s in valid if s.identity == (outdoor_cycle, indoor_address)]

    if len(matches) > 1:
        preferred = [s for s in matches if s.slot == stored_slot]
        if preferred:
            return SlotResolution(preferred[0])
        return SlotResolution(None, REASON_AMBIGUOUS)
    if matches:
        return SlotResolution(matches[0])
    if not is_settled(table):
        return SlotResolution(None, REASON_NOT_SETTLED)
    return SlotResolution(None, REASON_NOT_FOUND)
