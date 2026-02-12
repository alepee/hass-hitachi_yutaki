"""Compressor timing calculation service.

Pure business logic isolated from infrastructure concerns.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from ..models.timing import CompressorTimingResult
from ..ports.storage import Storage


class CompressorHistory:
    """Tracks compressor state history for timing calculations."""

    def __init__(
        self, storage: Storage[tuple[datetime, bool]], max_history: int
    ) -> None:
        """Initialize the history.

        Args:
            storage: Storage implementation for state history
            max_history: Maximum number of timing records to keep

        """
        self._storage = storage
        self.max_history = max_history
        self._cycles: list[float] = []  # minutes
        self._run_times: list[float] = []  # minutes
        self._rest_times: list[float] = []  # minutes

    def add_state(self, is_running: bool, timestamp: datetime | None = None) -> None:
        """Add a new compressor state to history.

        Args:
            is_running: Whether the compressor is currently running
            timestamp: Optional timestamp to use (defaults to datetime.now)

        """
        now = timestamp or datetime.now()
        states = self._storage.get_all()

        # If we have a previous state
        if states:
            last_time, last_state = states[-1]

            # Only add if state changed
            if last_state != is_running:
                duration = (now - last_time).total_seconds() / 60  # Convert to minutes

                # Calculate times based on the state change
                if is_running:  # Changing from off to on
                    if len(states) >= 2:  # We have a complete cycle
                        cycle_start = next(
                            (
                                time for time, state in reversed(states[:-1]) if state
                            ),  # Find last running state
                            None,
                        )
                        if cycle_start:
                            cycle_time = (now - cycle_start).total_seconds() / 60
                            self._cycles.append(cycle_time)
                    self._rest_times.append(duration)
                else:  # Changing from on to off
                    self._run_times.append(duration)

                # Add the new state
                self._storage.append((now, is_running))

                # Trim timing lists
                if len(self._cycles) > self.max_history:
                    self._cycles.pop(0)
                if len(self._run_times) > self.max_history:
                    self._run_times.pop(0)
                if len(self._rest_times) > self.max_history:
                    self._rest_times.pop(0)
        else:
            # First state
            self._storage.append((now, is_running))

    def bulk_load(self, states: Iterable[tuple[datetime, bool]]) -> None:
        """Load historical compressor states."""
        for timestamp, is_running in sorted(states, key=lambda state: state[0]):
            self.add_state(is_running, timestamp=timestamp)

    def get_average_times(self) -> tuple[float | None, float | None, float | None]:
        """Get average cycle, run and rest times.

        Returns:
            Tuple of (average_cycle_time, average_runtime, average_resttime) in minutes

        """
        avg_cycle = sum(self._cycles) / len(self._cycles) if self._cycles else None
        avg_run = (
            sum(self._run_times) / len(self._run_times) if self._run_times else None
        )
        avg_rest = (
            sum(self._rest_times) / len(self._rest_times) if self._rest_times else None
        )
        return avg_cycle, avg_run, avg_rest

    def clear(self) -> None:
        """Clear all timing history."""
        # Clear the calculated timing lists
        # Note: Storage itself is not cleared to preserve state persistence
        self._cycles.clear()
        self._run_times.clear()
        self._rest_times.clear()


class CompressorTimingService:
    """Compressor timing calculation service.

    This service is independent of Home Assistant and can be easily tested.
    """

    def __init__(self, history: CompressorHistory) -> None:
        """Initialize the compressor timing service.

        Args:
            history: Compressor history tracker

        """
        self._history = history

    def update(self, compressor_frequency: float | None) -> None:
        """Update compressor state based on current frequency.

        Args:
            compressor_frequency: Current compressor frequency in Hz.
                                  None or 0 means compressor is not running.

        """
        is_running = compressor_frequency is not None and compressor_frequency > 0
        self._history.add_state(is_running)

    def get_timing(self) -> CompressorTimingResult:
        """Get current timing statistics.

        Returns:
            Compressor timing result with average times

        """
        avg_cycle, avg_run, avg_rest = self._history.get_average_times()
        return CompressorTimingResult(
            cycle_time=avg_cycle,
            runtime=avg_run,
            resttime=avg_rest,
        )

    def preload_states(self, states: Iterable[tuple[datetime, bool]]) -> None:
        """Preload historical compressor states (used for Recorder replay)."""
        self._history.bulk_load(states)
