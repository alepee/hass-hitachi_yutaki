"""Tests for telemetry collector (dict-based)."""

from datetime import UTC, datetime, timedelta
import json
import logging
from pathlib import Path

import pytest

from custom_components.hitachi_yutaki.telemetry.collector import (
    MAX_FLUSH_BYTES,
    MAX_FLUSH_POINTS,
    MAX_POINT_AGE,
    TelemetryCollector,
    compute_buffer_max_size,
    compute_collect_stride,
)
from custom_components.hitachi_yutaki.telemetry.models import (
    MetricsBatch,
    TelemetryLevel,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "yutampo_r32_atw_mbs_02_snapshot.json"


def _sample_data(**overrides) -> dict:
    """Create a sample coordinator data dict."""
    data = {
        "is_available": True,
        "outdoor_temp": 5.5,
        "water_inlet_temp": 35.0,
        "water_outlet_temp": 40.5,
        "dhw_current_temp": 52.0,
        "compressor_frequency": 65.0,
        "compressor_current": 8.5,
        "unit_mode": 1,
        "operation_state": "operation_state_heat_thermo_on",
        "thermal_power_heating": 5.2,
        "electrical_power": 1.8,
        "cop_heating": 1.32,
        "is_compressor_running": True,
        "is_defrosting": False,
    }
    data.update(overrides)
    return data


class TestCollectorLevel:
    """Tests for level-based collection behavior."""

    def test_off_does_not_collect(self):
        """OFF level ignores all data."""
        collector = TelemetryCollector(TelemetryLevel.OFF)
        collector.collect(_sample_data())
        assert collector.buffer_size == 0

    def test_on_collects(self):
        """ON level collects data."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        assert collector.buffer_size == 1


class TestDictCollection:
    """Tests for dict-based data collection."""

    def test_preserves_data_keys(self):
        """Collected dict preserves all data keys from coordinator."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        point = collector.flush()[0]
        assert point["outdoor_temp"] == 5.5
        assert point["water_inlet_temp"] == 35.0
        assert point["cop_heating"] == 1.32
        assert point["thermal_power_heating"] == 5.2

    def test_is_available_excluded(self):
        """The internal 'is_available' key is stripped."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        point = collector.flush()[0]
        assert "is_available" not in point

    def test_timestamp_added(self):
        """Each collected dict gets a UTC timestamp."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        point = collector.flush()[0]
        assert "time" in point
        assert point["time"].tzinfo == UTC

    def test_original_data_not_mutated(self):
        """collect() does not mutate the original data dict."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        data = _sample_data()
        original_keys = set(data.keys())
        collector.collect(data)
        assert set(data.keys()) == original_keys
        assert "time" not in data

    def test_skips_unavailable_data(self):
        """Data marked unavailable is not collected."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect({"is_available": False, "outdoor_temp": 10})
        assert collector.buffer_size == 0

    def test_skips_empty_data(self):
        """Empty data dict is not collected."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect({})
        assert collector.buffer_size == 0


class TestCollectorBuffer:
    """Tests for buffer behavior."""

    def test_flush_returns_and_clears(self):
        """flush() returns all buffered dicts and empties the buffer."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        collector.collect(_sample_data())
        assert collector.buffer_size == 2
        points = collector.flush()
        assert len(points) == 2
        assert collector.buffer_size == 0

    def test_flush_empty_returns_empty_list(self):
        """Flushing empty buffer returns empty list."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        assert collector.flush() == []

    def test_buffer_overflow_drops_oldest(self):
        """Oldest dicts are dropped when buffer exceeds max size."""
        collector = TelemetryCollector(TelemetryLevel.ON, buffer_max_size=3)
        for i in range(5):
            collector.collect(_sample_data(outdoor_temp=float(i)))
        assert collector.buffer_size == 3
        points = collector.flush()
        assert points[0]["outdoor_temp"] == 2.0
        assert points[2]["outdoor_temp"] == 4.0


class TestRequeue:
    """Failed sends put their points back (#395)."""

    def test_requeued_points_are_returned_by_the_next_flush(self):
        """A failed batch is not lost."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        points = collector.flush()
        assert collector.buffer_size == 0

        collector.requeue(points)
        assert collector.buffer_size == 1
        assert collector.flush() == points

    def test_requeued_points_come_before_newer_ones(self):
        """Chronological order is preserved across a failed send."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data(outdoor_temp=1.0))
        failed = collector.flush()
        collector.collect(_sample_data(outdoor_temp=2.0))

        collector.requeue(failed)
        result = collector.flush()
        assert [p["outdoor_temp"] for p in result] == [1.0, 2.0]

    def test_stale_points_are_dropped(self):
        """Points older than MAX_POINT_AGE have no analytical value.

        This is also the guard that stops a broken installation from
        replaying garbage forever: when a gateway loses its unit every
        register reads 0xFFFF, and those points are collected as valid.
        """
        collector = TelemetryCollector(TelemetryLevel.ON)
        stale = dict(_sample_data())
        stale["time"] = datetime.now(tz=UTC) - MAX_POINT_AGE - timedelta(seconds=1)
        fresh = dict(_sample_data())
        fresh["time"] = datetime.now(tz=UTC)

        collector.requeue([stale, fresh])
        assert collector.buffer_size == 1
        assert collector.flush() == [fresh]

    def test_overflow_keeps_the_newest_points(self):
        """Regression guard: deque.extendleft evicts the NEWEST points.

        appendleft/extendleft on a bounded deque drop from the right, which
        is the opposite of what is wanted here, so requeue must rebuild the
        buffer explicitly.
        """
        collector = TelemetryCollector(TelemetryLevel.ON, buffer_max_size=3)
        for i in range(3):
            collector.collect(_sample_data(outdoor_temp=float(i)))

        old = [{**_sample_data(outdoor_temp=-1.0), "time": datetime.now(tz=UTC)}]
        collector.requeue(old)

        assert collector.buffer_size == 3
        assert [p["outdoor_temp"] for p in collector.flush()] == [0.0, 1.0, 2.0]

    def test_requeue_of_an_empty_list_is_a_noop(self):
        """Nothing to put back, nothing changes."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(_sample_data())
        collector.requeue([])
        assert collector.buffer_size == 1


class TestFlushCap:
    """A flush is bounded in size, so a backlog cannot outgrow the endpoint.

    The ingestion endpoint rejects a decompressed body over 256 KB with HTTP
    413. Re-queueing (#395) means a failed cycle adds its points back, so
    without a cap the batch grows until every send is rejected and telemetry
    never recovers.
    """

    def test_flush_returns_at_most_max_flush_points(self):
        """A full buffer is drained in capped slices, oldest first."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        total = MAX_FLUSH_POINTS + 25
        for i in range(total):
            collector.collect(_sample_data(outdoor_temp=float(i)))

        first = collector.flush()
        assert len(first) == MAX_FLUSH_POINTS
        assert [p["outdoor_temp"] for p in first] == [
            float(i) for i in range(MAX_FLUSH_POINTS)
        ]

        # The remainder stays buffered, nothing is lost.
        assert collector.buffer_size == total - MAX_FLUSH_POINTS
        second = collector.flush()
        assert [p["outdoor_temp"] for p in second] == [
            float(i) for i in range(MAX_FLUSH_POINTS, total)
        ]
        assert collector.buffer_size == 0

    def test_flush_below_the_cap_returns_everything(self):
        """The cap does not change the normal small-batch behaviour."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        for _ in range(3):
            collector.collect(_sample_data())
        assert len(collector.flush()) == 3
        assert collector.buffer_size == 0

    def test_repeated_failures_cannot_grow_the_batch(self):
        """Simulated failure loop: every batch stays at or under the cap.

        Each cycle collects a poll's worth of points and re-queues the batch
        the "send" rejected, which is exactly the shape of a sustained outage.
        """
        collector = TelemetryCollector(TelemetryLevel.ON)
        sizes = []
        for _ in range(10):
            for _ in range(60):  # one 5-minute cycle at the default 5s poll
                collector.collect(_sample_data())
            batch = collector.flush()
            sizes.append(len(batch))
            collector.requeue(batch)  # the send failed

        assert max(sizes) <= MAX_FLUSH_POINTS

    def test_narrowest_profile_batch_stays_well_under_the_limit(self):
        """Real field data on the narrowest profile, as a sanity check.

        MAX_PAYLOAD_SIZE in backend/worker/src/validator.ts is 256 KB of
        decompressed body; over it the Worker answers HTTP 413. The register
        values come from a real anonymized Yutampo R32 snapshot, which is the
        *narrowest* profile in the repo at 41 keys. It is therefore not a
        worst case, and the point count alone never was the binding bound:
        TestFlushByteBudget carries that invariant.
        """
        max_payload_size = 256 * 1024  # source: backend/worker/src/validator.ts
        registers = json.loads(_FIXTURE.read_text())["registers"]

        collector = TelemetryCollector(TelemetryLevel.ON)
        for _ in range(MAX_FLUSH_POINTS + 10):
            collector.collect({"is_available": True, **registers})

        batch = MetricsBatch(
            instance_hash="a" * 64, device_hash="b" * 64, points=collector.flush()
        )
        size = len(json.dumps(batch.to_dict()).encode())

        assert len(batch.points) == MAX_FLUSH_POINTS
        assert size < max_payload_size / 2, (
            f"a {MAX_FLUSH_POINTS}-point batch serializes to {size} bytes, "
            f"too close to the {max_payload_size}-byte ingestion limit"
        )


class TestCollectStride:
    """Collection is decimated when the poll outruns the drain rate (#395).

    The scan interval is a user setting with no lower bound, while a flush
    sends at most MAX_FLUSH_POINTS every 5 minutes. Below roughly 3.75s the
    poll produces more points per cycle than a flush can take, so the buffer
    saturates and the deque evicts points silently and forever.
    """

    def test_default_poll_collects_every_point(self):
        """The documented 5s poll must be untouched by the stride."""
        assert compute_collect_stride(timedelta(seconds=5), timedelta(minutes=5)) == 1

    def test_slow_polls_collect_every_point(self):
        """Anything slower than the default fits under the cap by construction."""
        for seconds in (4, 10, 30, 60):
            assert (
                compute_collect_stride(timedelta(seconds=seconds), timedelta(minutes=5))
                == 1
            ), f"a {seconds}s poll should not be decimated"

    def test_fast_polls_are_decimated(self):
        """A cycle can never hand the flush more points than it can send."""
        for seconds in (1, 2, 3):
            stride = compute_collect_stride(
                timedelta(seconds=seconds), timedelta(minutes=5)
            )
            per_cycle = (300 / seconds) / stride
            assert per_cycle <= MAX_FLUSH_POINTS, (
                f"a {seconds}s poll still produces {per_cycle} points per cycle"
            )

    def test_degenerate_intervals_fall_back_to_every_point(self):
        """A zero interval must not divide by zero or silence collection."""
        assert compute_collect_stride(timedelta(0), timedelta(minutes=5)) == 1
        assert compute_collect_stride(timedelta(seconds=5), timedelta(0)) == 1

    def test_stride_keeps_one_poll_out_of_n(self):
        """Decimation is even, not bursty."""
        collector = TelemetryCollector(TelemetryLevel.ON, collect_stride=3)
        for i in range(9):
            collector.collect(_sample_data(outdoor_temp=float(i)))

        assert [p["outdoor_temp"] for p in collector.flush()] == [2.0, 5.0, 8.0]

    def test_unavailable_polls_do_not_shift_the_stride(self):
        """A gateway blackout must not change which polls are kept."""
        collector = TelemetryCollector(TelemetryLevel.ON, collect_stride=2)
        collector.collect(_sample_data(outdoor_temp=0.0))
        collector.collect({"is_available": False})
        collector.collect(_sample_data(outdoor_temp=1.0))

        assert [p["outdoor_temp"] for p in collector.flush()] == [1.0]

    def test_a_fast_poll_no_longer_saturates_the_buffer(self):
        """End-to-end: a 2s poll used to lose ~half its points forever.

        Ten cycles of a 2s poll against a working endpoint: with a stride of
        1 the buffer pins at its maximum and `collect` evicts on every call.
        """
        stride = compute_collect_stride(timedelta(seconds=2), timedelta(minutes=5))
        collector = TelemetryCollector(TelemetryLevel.ON, collect_stride=stride)

        sent = 0
        for _ in range(10):
            for _ in range(150):  # one 5-minute cycle at a 2s poll
                collector.collect(_sample_data())
            sent += len(collector.flush())  # the send succeeds

        assert collector.points_dropped == 0
        assert collector.buffer_size == 0
        assert sent == 10 * 150 // stride


class TestOverflowIsVisible:
    """A saturated buffer must be reported, not silently absorbed (#395)."""

    def test_collect_counts_evicted_points(self):
        """deque.append drops the oldest point without a word."""
        collector = TelemetryCollector(TelemetryLevel.ON, buffer_max_size=2)
        for _ in range(5):
            collector.collect(_sample_data())

        assert collector.buffer_size == 2
        assert collector.points_dropped == 3

    def test_requeue_counts_evicted_points(self):
        """Overflow on re-queue is the same loss and gets the same accounting."""
        collector = TelemetryCollector(TelemetryLevel.ON, buffer_max_size=2)
        for _ in range(2):
            collector.collect(_sample_data())

        collector.requeue([{**_sample_data(), "time": datetime.now(tz=UTC)}])

        assert collector.buffer_size == 2
        assert collector.points_dropped == 1

    def test_first_eviction_warns(self, caplog):
        """The very first dropped point already produces a log line."""
        collector = TelemetryCollector(TelemetryLevel.ON, buffer_max_size=1)
        collector.collect(_sample_data())

        with caplog.at_level(logging.WARNING):
            collector.collect(_sample_data())

        assert "buffer full" in caplog.text

    def test_a_healthy_collector_never_warns(self, caplog):
        """No noise on the nominal path."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        with caplog.at_level(logging.WARNING):
            for _ in range(60):
                collector.collect(_sample_data())

        assert collector.points_dropped == 0
        assert caplog.text == ""


class TestFlushByteBudget:
    """A request body is bounded in bytes, not only in points (#395).

    A point carries one field per register plus the derived metrics, so its
    size is a property of the heat-pump profile: about 1.1 KB on the narrowest
    profile in the repo and about 3 KB on the widest register map. A fixed
    point count therefore leaves a margin that varies with the profile, and 80
    points of the widest measure roughly 233 KB against the endpoint's 256 KB.
    The byte budget is what makes the bound hold on any profile.
    """

    @staticmethod
    def _point(keys: int) -> dict:
        """Build a point of a given width with realistic value sizes."""
        return {f"register_key_number_{i:03d}": 1234.5 for i in range(keys)}

    @pytest.mark.parametrize("keys_per_point", [41, 95, 200, 500])
    def test_a_flush_never_exceeds_the_ingestion_limit(self, keys_per_point):
        """The invariant, across widths well beyond any current profile.

        Today's widest register map is around 95 register keys plus roughly 25
        derived metrics. The parametrization runs past that on purpose: the
        bound must hold for profiles this repo does not have yet.
        """
        max_payload_size = 256 * 1024  # backend/worker/src/validator.ts
        collector = TelemetryCollector(TelemetryLevel.ON, buffer_max_size=1000)
        for _ in range(500):
            collector.collect({"is_available": True, **self._point(keys_per_point)})

        batch = MetricsBatch(
            instance_hash="a" * 64, device_hash="b" * 64, points=collector.flush()
        )
        size = len(json.dumps(batch.to_dict()).encode())

        assert size < max_payload_size, (
            f"{len(batch.points)} points of {keys_per_point} keys serialize to "
            f"{size} bytes, over the {max_payload_size}-byte ingestion limit"
        )

    def test_a_wide_profile_sends_fewer_points(self):
        """The byte budget, not the point count, is what binds on a wide one."""
        collector = TelemetryCollector(TelemetryLevel.ON, buffer_max_size=1000)
        for _ in range(500):
            collector.collect({"is_available": True, **self._point(95)})

        assert len(collector.flush()) < MAX_FLUSH_POINTS

    def test_a_narrow_profile_is_still_bound_by_the_point_cap(self):
        """Small points must not let a single request carry hundreds of them."""
        collector = TelemetryCollector(TelemetryLevel.ON, buffer_max_size=1000)
        for _ in range(500):
            collector.collect({"is_available": True, **self._point(10)})

        assert len(collector.flush()) == MAX_FLUSH_POINTS

    def test_an_oversized_point_still_goes_out_alone(self):
        """A point bigger than the whole budget must not block the buffer."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect({"is_available": True, "blob": "x" * (MAX_FLUSH_BYTES + 1)})
        collector.collect({"is_available": True, "blob": "y"})

        assert len(collector.flush()) == 1
        assert collector.buffer_size == 1

    def test_an_empty_buffer_flushes_nothing(self):
        """No point to measure, no request."""
        assert TelemetryCollector(TelemetryLevel.ON).flush() == []


class TestBufferWindow:
    """The buffer window and the age cutoff must express the same rule (#395)."""

    def test_default_poll_keeps_the_documented_size(self):
        """5s poll: 30 minutes is the 360 points the constant documents."""
        assert compute_buffer_max_size(timedelta(seconds=5)) == 360

    def test_slow_poll_holds_the_same_duration_not_the_same_count(self):
        """60s poll: 360 points would be six hours, requeue drops after 30 min."""
        assert compute_buffer_max_size(timedelta(seconds=60)) == 30

    def test_stride_is_taken_into_account(self):
        """What matters is the collected cadence, not the poll cadence."""
        assert compute_buffer_max_size(timedelta(seconds=1), stride=4) == 450

    def test_window_always_covers_several_flush_cycles(self):
        """MAX_POINT_AGE is 30 min against a 5 min flush, so at least six."""
        for seconds in (1, 2, 5, 15, 30, 60, 300):
            interval = timedelta(seconds=seconds)
            stride = compute_collect_stride(interval, timedelta(minutes=5))
            per_cycle = (300 / seconds) / stride
            assert compute_buffer_max_size(interval, stride) >= per_cycle * 6

    def test_degenerate_interval_falls_back_to_the_default(self):
        """A zero interval must not divide by zero."""
        assert compute_buffer_max_size(timedelta(0)) == 360
