"""Tests for the unit identity guard: a proof holds for one connection (#476)."""

from __future__ import annotations

from custom_components.hitachi_yutaki.domain.services.unit_identity import (
    UNIT_CHECK_INTERVAL_S,
    UnitIdentityGuard,
    UnverifiedVerdict,
)
from tests.domain.clock import FakeClock


def _guard() -> tuple[UnitIdentityGuard, FakeClock]:
    clock = FakeClock()
    return UnitIdentityGuard(clock), clock


def test_first_readings_are_checked():
    """Nothing is proven before the first check."""
    guard, _ = _guard()

    assert guard.is_due(1)


def test_proof_holds_on_the_same_connection_until_the_interval():
    """A proven unit is re-checked periodically while the connection stays."""
    guard, clock = _guard()
    guard.proven(1)

    clock.seconds += UNIT_CHECK_INTERVAL_S - 1
    assert not guard.is_due(1)
    clock.seconds += 1
    assert guard.is_due(1)


def test_a_new_connection_voids_the_proof_at_once():
    """A reconnection one second after a proof still requires a new check."""
    guard, clock = _guard()
    guard.proven(1)

    clock.seconds += 1
    assert guard.is_due(2)


def test_forced_check_is_due_on_the_same_connection():
    """A failed poll forces a check even on an unchanged connection."""
    guard, _ = _guard()
    guard.proven(1)

    guard.force_check()

    assert guard.is_due(1)


def test_clock_going_backwards_counts_as_elapsed():
    """Invalid elapsed time never extends the trust in a proof."""
    guard, clock = _guard()
    guard.proven(1)

    clock.seconds -= 5

    assert guard.is_due(1)


def test_inconclusive_check_on_the_proven_connection_publishes():
    """An unreadable check on an unchanged connection is a transient hiccup."""
    guard, _ = _guard()
    guard.proven(1)
    guard.force_check()

    assert guard.unverified(1) is UnverifiedVerdict.PUBLISH


def test_inconclusive_check_after_a_reconnection_withholds():
    """After a reconnection, readings the unit check could not confirm are withheld."""
    guard, _ = _guard()
    guard.proven(1)

    assert guard.unverified(2) is UnverifiedVerdict.WITHHOLD
    # And the next poll on that connection checks again.
    assert guard.is_due(2)


def test_inconclusive_check_without_any_proof_keeps_the_setup_binding():
    """Before any runtime proof, the binding made at setup stands."""
    guard, _ = _guard()

    assert guard.unverified(3) is UnverifiedVerdict.PUBLISH


def test_inconclusive_check_after_a_reconnection_withholds_without_any_proof():
    """The setup binding only stands on the connection of the first readings.

    When the first check is inconclusive the unit is never proven; a later
    reconnection is still exactly when the unit may have moved, so readings
    whose check fails there are withheld like after a proof.
    """
    guard, _ = _guard()

    assert guard.unverified(1) is UnverifiedVerdict.PUBLISH
    assert guard.unverified(1) is UnverifiedVerdict.PUBLISH
    assert guard.unverified(2) is UnverifiedVerdict.WITHHOLD
    assert guard.is_due(2)


def test_a_proof_after_an_unproven_start_takes_over():
    """Once proven, the proof's connection is the trusted one."""
    guard, _ = _guard()
    guard.unverified(1)
    guard.proven(2)

    assert guard.unverified(2) is UnverifiedVerdict.PUBLISH
    assert guard.unverified(1) is UnverifiedVerdict.WITHHOLD
