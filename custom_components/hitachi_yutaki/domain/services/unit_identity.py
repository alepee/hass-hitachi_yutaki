"""When the identity of the polled unit must be proven again (#476).

A gateway hosting several units can move them to other addresses when it
reboots, and a reboot always drops the connection. A unit proven on one
connection is therefore only trusted on that connection: any new connection
(a reconnection, whether the client asked for it or the transport made it on
its own) requires a new proof before its readings are published. A periodic
re-check backs this up while the connection stays the same.

The connection is identified by an opaque epoch supplied by the caller, which
changes whenever the underlying connection is replaced.
"""

from __future__ import annotations

from enum import StrEnum

from ..ports.clock import Clock

# How often a healthy connection re-checks the unit, in seconds.
UNIT_CHECK_INTERVAL_S = 60.0


class UnverifiedVerdict(StrEnum):
    """What to do with readings whose unit check could not be made."""

    # Publish: the connection is the one the unit was last proven on (or no
    # proof was ever obtained at runtime, the setup binding stands).
    PUBLISH = "publish"
    # Withhold: the connection changed since the last proof, the readings may
    # come from another unit.
    WITHHOLD = "withhold"


class UnitIdentityGuard:
    """Track the proof that the polled unit is still the bound one.

    Pure policy: the caller performs the check and reports its outcome.
    """

    def __init__(self, clock: Clock, interval: float = UNIT_CHECK_INTERVAL_S) -> None:
        """Initialize with no proof: the first poll checks the unit."""
        self._clock = clock
        self._interval = interval
        # Connection epoch the unit was last proven on, None before any proof.
        self._proven_epoch: int | None = None
        # Monotonic time of the last proof, None to force a check.
        self._proven_at: float | None = None

    def is_due(self, epoch: int) -> bool:
        """Return whether readings taken on connection ``epoch`` need a check.

        Due when the unit was never proven, when the connection changed since
        the proof, when a check was forced, or once the interval has elapsed.
        A clock going backwards counts as elapsed.
        """
        if self._proven_at is None or self._proven_epoch != epoch:
            return True
        elapsed = self._clock.monotonic() - self._proven_at
        return elapsed < 0 or elapsed >= self._interval

    def proven(self, epoch: int) -> None:
        """Record that the unit was proven on connection ``epoch``."""
        self._proven_epoch = epoch
        self._proven_at = self._clock.monotonic()

    def force_check(self) -> None:
        """Check the unit on the next poll, e.g. after a failed one."""
        self._proven_at = None

    def unverified(self, epoch: int) -> UnverifiedVerdict:
        """Decide on readings from connection ``epoch`` whose check failed.

        An inconclusive check on the connection the unit was proven on is a
        transient hiccup. On any other connection the readings are withheld,
        since a reconnection is exactly when the unit may have moved.
        """
        if self._proven_epoch is None or self._proven_epoch == epoch:
            return UnverifiedVerdict.PUBLISH
        return UnverifiedVerdict.WITHHOLD
