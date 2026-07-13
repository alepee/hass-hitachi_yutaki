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

    def test_live_then_rehydrate_seam_stays_non_negative(self):
        """The real reachable trigger: a live reading, then replay of OLDER states.

        On startup the coordinator does one live poll (stores a state at ~now),
        then rehydration replays the last ~6h of Recorder states via
        preload_states. bulk_load only sorts its own iterable, so the first
        replayed (older) state lands after the live "now" entry and yields a
        large negative duration at the seam. This is exactly the -360 min value
        the telemetry archive showed; the guard must absorb it. This test fails
        on the pre-fix code (the -360 was averaged into rest/run time).
        """
        base = datetime(2026, 7, 1, 13, 0, 0)
        history = _history()
        # Live poll first: a running state stored at ~now (13:00).
        history.add_state(True, timestamp=base)
        # Rehydration then replays OLDER Recorder states (07:00..10:00).
        history.bulk_load(
            [
                (base - timedelta(hours=6), False),
                (base - timedelta(hours=5), True),
                (base - timedelta(hours=4), False),
                (base - timedelta(hours=3), True),
            ]
        )

        cycle, run, rest = history.get_average_times()
        for value in (cycle, run, rest):
            assert value is None or value >= 0
        # The valid post-seam transitions still produce real positive averages.
        assert run == 60
        assert rest == 60
