"""Defrost guard service for filtering unreliable data during defrost cycles.

Pure business logic isolated from infrastructure concerns.
Centralizes defrost+recovery filtering upstream of both COP and thermal services.
"""

from __future__ import annotations

from enum import Enum

from ..ports.clock import Clock


class DefrostState(Enum):
    """State of the defrost guard."""

    NORMAL = "normal"
    DEFROST = "defrost"
    RECOVERY = "recovery"


class DefrostGuard:
    """Guard that tracks defrost state and signals when data is unreliable.

    State machine with three states:
    - NORMAL: data flows normally
    - DEFROST: heat pump is actively defrosting (ΔT inverts)
    - RECOVERY: defrost ended but ΔT not yet stabilized

    Transitions:
    - NORMAL → DEFROST: when is_defrosting becomes True
    - DEFROST → RECOVERY: when is_defrosting becomes False
    - RECOVERY → NORMAL: after stable_readings_required consecutive readings
      with ΔT sign matching pre-defrost sign, OR recovery_timeout elapsed
    - RECOVERY → DEFROST: if is_defrosting goes back to True
    """

    def __init__(
        self,
        stable_readings_required: int = 3,
        recovery_timeout: float = 300.0,
        *,
        clock: Clock | None = None,
    ) -> None:
        """Initialize the defrost guard.

        Args:
            clock: Injected time source for live measurements.
            stable_readings_required: Number of consecutive readings with consistent
                ΔT sign needed to exit recovery (default: 3, ~15s at 5s polling)
            recovery_timeout: Maximum time in seconds to stay in recovery before
                forcing return to NORMAL (default: 300.0 = 5 minutes)

        """
        self._clock = clock
        self._stable_readings_required = stable_readings_required
        self._recovery_timeout = recovery_timeout
        self._state = DefrostState.NORMAL
        self._pre_defrost_sign: bool | None = None  # True = positive (heating)
        self._stable_count = 0
        self._recovery_start_time: float = 0.0

    @property
    def state(self) -> DefrostState:
        """Return the current defrost state for diagnostics."""
        return self._state

    @property
    def is_data_reliable(self) -> bool:
        """Return True only when state is NORMAL."""
        return self._state == DefrostState.NORMAL

    def update(
        self,
        is_defrosting: bool,
        delta_t: float | None,
        *,
        timestamp: float | None = None,
        new_temperature_sample: bool = True,
    ) -> None:
        """Update the defrost guard with fresh data.

        Call once per polling cycle.

        Args:
            timestamp: Optional explicit elapsed seconds for replay.
            is_defrosting: Whether the heat pump is currently defrosting
            delta_t: Water outlet minus water inlet temperature, or None if unavailable
            new_temperature_sample: Whether delta_t is a fresh thermal observation.
                Other events may advance the timeout but cannot prove stability.

        """
        if timestamp is None:
            if self._clock is None:
                raise ValueError("An injected clock or explicit timestamp is required")
            timestamp = self._clock.monotonic()
        if self._state == DefrostState.NORMAL:
            self._handle_normal(is_defrosting, delta_t)
        elif self._state == DefrostState.DEFROST:
            self._handle_defrost(is_defrosting, timestamp)
        elif self._state == DefrostState.RECOVERY:
            self._handle_recovery(
                is_defrosting, delta_t, timestamp, new_temperature_sample
            )

    def _handle_normal(self, is_defrosting: bool, delta_t: float | None) -> None:
        """Handle NORMAL state transitions."""
        if is_defrosting:
            # Remember ΔT sign before entering defrost
            if delta_t is not None:
                self._pre_defrost_sign = delta_t > 0
            self._state = DefrostState.DEFROST
        # Otherwise stay NORMAL — nothing to do

    def _handle_defrost(self, is_defrosting: bool, timestamp: float) -> None:
        """Handle DEFROST state transitions."""
        if not is_defrosting:
            # Defrost ended, enter recovery
            self._state = DefrostState.RECOVERY
            self._stable_count = 0
            self._recovery_start_time = timestamp
        # Otherwise stay in DEFROST

    def _handle_recovery(
        self,
        is_defrosting: bool,
        delta_t: float | None,
        timestamp: float,
        new_temperature_sample: bool,
    ) -> None:
        """Handle RECOVERY state transitions."""
        if is_defrosting:
            # Defrost restarted
            self._state = DefrostState.DEFROST
            self._stable_count = 0
            return

        # Check safety timeout
        if timestamp - self._recovery_start_time >= self._recovery_timeout:
            self._state = DefrostState.NORMAL
            self._stable_count = 0
            return

        # Check ΔT stabilization
        if delta_t is None or self._pre_defrost_sign is None:
            # Can't assess stability
            self._stable_count = 0
            return

        # Use ±0.5°C threshold (same as _detect_mode_from_temperatures)
        current_sign = delta_t > 0.5 if self._pre_defrost_sign else delta_t < -0.5

        if current_sign:
            if not new_temperature_sample:
                return
            self._stable_count += 1
            if self._stable_count >= self._stable_readings_required:
                self._state = DefrostState.NORMAL
                self._stable_count = 0
        else:
            self._stable_count = 0
