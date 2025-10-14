"""Compressor cycle and timing logic for Hitachi Yutaki."""

from datetime import datetime

from .storage import AbstractStorage


class CompressorHistory:
    """Class to track compressor history."""

    def __init__(
        self, storage: AbstractStorage[tuple[datetime, bool]], max_history: int
    ) -> None:
        """Initialize the history."""
        self._storage = storage
        self.max_history = max_history
        self._cycles: list[float] = []  # minutes
        self._run_times: list[float] = []  # minutes
        self._rest_times: list[float] = []  # minutes

    def add_state(self, is_running: bool) -> None:
        """Add a new state to history."""
        now = datetime.now()
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

    def get_average_times(self) -> tuple[float | None, float | None, float | None]:
        """Get average cycle, run and rest times."""
        avg_cycle = sum(self._cycles) / len(self._cycles) if self._cycles else None
        avg_run = (
            sum(self._run_times) / len(self._run_times) if self._run_times else None
        )
        avg_rest = (
            sum(self._rest_times) / len(self._rest_times) if self._rest_times else None
        )
        return avg_cycle, avg_run, avg_rest

    def clear(self) -> None:
        """Clear all history."""
        # This is a bit tricky with abstracted storage.
        # A full clear might not be what we want with persistence.
        # For now, we clear the calculated timing lists.
        # A better `clear` on the storage might be needed in the future.
        self._cycles.clear()
        self._run_times.clear()
        self._rest_times.clear()
