"""Tests for the compressor timing service.

Focus on the negative-duration guard (issue #365): a Recorder-replayed state
whose local wall-clock timestamp lands after a subsequent live reading (clock or
DST shift) must never produce a negative average rest/run/cycle time.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from custom_components.hitachi_yutaki.adapters.storage.in_memory import InMemoryStorage
from custom_components.hitachi_yutaki.domain.services.timing import (
    CompressorHistory,
    CompressorTimingService,
)


def _history() -> CompressorHistory:
    return CompressorHistory(InMemoryStorage(), max_history=10)


class TestNegativeDurationGuard:
    """A transition going back in time must not corrupt the averages."""

    def test_out_of_order_rest_time_is_ignored(self):
        """An off->on transition with a past timestamp yields no negative rest."""
        base = datetime(2026, 7, 1, 12, 0, 0)
        history = _history()
        # on, then off 10 min later -> a valid 10-min run time.
        history.add_state(True, timestamp=base)
        history.add_state(False, timestamp=base + timedelta(minutes=10))
        # off->on but the timestamp is BEFORE the last recorded state.
        history.add_state(True, timestamp=base + timedelta(minutes=5))

        _cycle, _run, rest = history.get_average_times()
        assert rest is None or rest >= 0

    def test_valid_sequence_still_computes(self):
        """A monotonic sequence still yields positive averages."""
        base = datetime(2026, 7, 1, 12, 0, 0)
        history = _history()
        history.add_state(True, timestamp=base)
        history.add_state(False, timestamp=base + timedelta(minutes=8))
        history.add_state(True, timestamp=base + timedelta(minutes=20))

        _cycle, run, rest = history.get_average_times()
        assert run == 8
        assert rest == 12

    def test_bulk_load_with_dst_backstep_stays_non_negative(self):
        """bulk_load over a backwards clock step never averages a negative."""
        base = datetime(2026, 10, 25, 2, 30, 0)  # DST-like fall-back window
        states = [
            (base, True),
            (base + timedelta(minutes=15), False),
            (base + timedelta(minutes=30), True),
            # Clock steps back one hour: timestamp precedes the previous one.
            (base - timedelta(minutes=45), False),
        ]
        service = CompressorTimingService(_history())
        service.preload_states(states)

        result = service.get_timing()
        for value in (result.cycle_time, result.runtime, result.resttime):
            assert value is None or value >= 0
