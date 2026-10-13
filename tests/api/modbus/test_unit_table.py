"""Tests for the HC-A(16/64)MB unit table decoding and slot resolution (#476)."""

from __future__ import annotations

import pytest

from custom_components.hitachi_yutaki.api.modbus.unit_table import (
    REASON_AMBIGUOUS,
    REASON_NOT_FOUND,
    REASON_NOT_SETTLED,
    UnitSlot,
    is_settled,
    parse_unit_table,
    resolve_slot,
)

EMPTY = [0, 255, 255, 255]


def _table(*slots: list[int]) -> list[UnitSlot]:
    return parse_unit_table([r for slot in slots for r in slot])


# Dump A from #476: 2x Yutaki S, 2x Yutampo R32.
DUMP_A = _table([1, 0, 0, 0], [1, 1, 1, 1], [1, 5, 6, 2], [1, 7, 8, 3], EMPTY, EMPTY)
# Yutaki S #1 (0, 0) absent at enumeration: every unit above it shifts down.
SHIFTED = _table([1, 1, 1, 0], [1, 5, 6, 1], [1, 7, 8, 2], EMPTY, EMPTY, EMPTY)


def test_parse_unit_table_decodes_descriptors() -> None:
    """Each 4-register descriptor decodes to [present, Ou, Iu, slot]."""
    slot = DUMP_A[2]
    assert (slot.slot, slot.present, slot.slot_echo) == (2, 1, 2)
    assert slot.identity == (5, 6)
    assert slot.is_valid
    assert DUMP_A[4].is_empty
    assert not DUMP_A[4].is_valid


def test_parse_unit_table_offsets_first_slot() -> None:
    """A partial read keeps the real slot indices."""
    assert parse_unit_table([1, 7, 8, 3], first_slot=3)[0].slot == 3


@pytest.mark.parametrize(
    "registers",
    [
        [1, 255, 255, 15],  # presence flag set on a cleared slot (#404)
        [1, 0, 0, 255],  # stale record not yet cleared (#404)
        [1, 5, 6, 3],  # slot echo disagrees with the slot index
    ],
)
def test_transient_slots_are_neither_valid_nor_empty(registers: list[int]) -> None:
    """Records seen mid re-enumeration are not trusted."""
    slot = parse_unit_table([*EMPTY, *registers])[1]
    assert not slot.is_valid
    assert not slot.is_empty
    assert not is_settled([slot])


def test_resolve_by_pair_follows_a_moved_unit() -> None:
    """The (Ou, Iu) pair is found in its new slot."""
    assert resolve_slot(DUMP_A, 1, 5, 6).slot == DUMP_A[2]
    assert resolve_slot(SHIFTED, 2, 5, 6).slot == SHIFTED[1]


def test_resolve_by_pair_never_reads_the_old_slot() -> None:
    """An absent unit is not found, even though its old slot is occupied."""
    resolution = resolve_slot(SHIFTED, 0, 0, 0)
    assert resolution.slot is None
    assert resolution.reason == REASON_NOT_FOUND


def test_resolve_reports_an_unsettled_table() -> None:
    """A missing unit in a table still being written is retried, not failed."""
    table = _table([1, 1, 1, 0], [1, 0, 0, 255], EMPTY)
    resolution = resolve_slot(table, 0, 0, 0)
    assert resolution.slot is None
    assert resolution.reason == REASON_NOT_SETTLED


def test_resolve_ignores_transient_slots_when_the_unit_is_found() -> None:
    """A transient slot elsewhere does not block a unit that is listed."""
    table = _table([1, 1, 1, 0], [1, 0, 0, 255], EMPTY)
    assert resolve_slot(table, 1, 1, 1).slot == table[0]


def test_resolve_legacy_entry_by_cycle() -> None:
    """Entries with only Ou (#353) are matched on their cycle."""
    assert resolve_slot(SHIFTED, 2, 7, None).slot == SHIFTED[2]


def test_resolve_legacy_entry_prefers_stored_slot_on_shared_cycle() -> None:
    """Several units on one cycle: the stored slot wins, else it is ambiguous."""
    table = _table([1, 3, 3, 0], [1, 3, 4, 1], EMPTY)
    assert resolve_slot(table, 1, 3, None).slot == table[1]
    resolution = resolve_slot(table, 2, 3, None)
    assert resolution.slot is None
    assert resolution.reason == REASON_AMBIGUOUS


def test_resolve_pre_353_entry_adopts_its_slot() -> None:
    """Entries with no identity at all keep their stored slot, if occupied."""
    assert resolve_slot(DUMP_A, 3, None, None).slot == DUMP_A[3]
    assert resolve_slot(DUMP_A, 5, None, None).reason == REASON_NOT_FOUND
