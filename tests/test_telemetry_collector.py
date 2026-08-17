"""Tests for telemetry collector (dict-based)."""

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

from custom_components.hitachi_yutaki.telemetry.collector import (
    MAX_FLUSH_POINTS,
    MAX_POINT_AGE,
    TelemetryCollector,
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

    def test_worst_case_batch_stays_under_the_ingestion_limit(self):
        """A full-cap batch of real field data must fit in one request.

        MAX_PAYLOAD_SIZE in backend/worker/src/validator.ts is 256 KB of
        decompressed body; over it the Worker answers HTTP 413. The register
        values come from a real anonymized Yutampo R32 snapshot, so this pins
        the client cap against the actual server limit.
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
