"""Tests for COP domain service — mode filtering via operation_mode."""

from datetime import UTC, datetime, timedelta

from custom_components.hitachi_yutaki.adapters.storage.in_memory import InMemoryStorage
from custom_components.hitachi_yutaki.domain.models.cop import (
    COPInput,
    PowerMeasurement,
)
from custom_components.hitachi_yutaki.domain.models.operation import (
    MODE_COOLING,
    MODE_DHW,
    MODE_HEATING,
    MODE_POOL,
)
from custom_components.hitachi_yutaki.domain.services.cop import (
    COP_MEASUREMENTS_HISTORY_SIZE,
    COP_MEASUREMENTS_INTERVAL,
    COP_MEASUREMENTS_PERIOD,
    COPService,
    EnergyAccumulator,
)
from tests.domain.clock import FakeClock


def _make_input(
    *,
    operation_mode: str | None = None,
    water_flow: float | None = 15.0,
) -> COPInput:
    """Create a COPInput with valid sensor data and the given operation_mode.

    ``water_flow`` defaults to a valid value; pass ``None`` to simulate a
    transient missing required input.
    """
    return COPInput(
        water_inlet_temp=30.0,
        water_outlet_temp=35.0,
        water_flow=water_flow,
        compressor_current=5.0,
        compressor_frequency=50.0,
        operation_mode=operation_mode,
    )


def _build_service(
    *, expected_mode: str | None = None, clock: FakeClock | None = None
) -> COPService:
    """Build a COPService with simple passthrough calculators."""
    storage: InMemoryStorage[PowerMeasurement] = InMemoryStorage(
        max_len=COP_MEASUREMENTS_HISTORY_SIZE,
    )
    accumulator = EnergyAccumulator(storage=storage, period=COP_MEASUREMENTS_PERIOD)

    # Simple calculators: thermal = |Tout - Tin| * flow * 0.001163, electrical = current * 230 / 1000
    def thermal_calc(inlet: float, outlet: float, flow: float) -> float:
        return abs(outlet - inlet) * flow * 1.163 / 1000

    def electrical_calc(current: float) -> float:
        return current * 230 / 1000

    return COPService(
        accumulator=accumulator,
        thermal_calculator=thermal_calc,
        electrical_calculator=electrical_calc,
        expected_mode=expected_mode,
        clock=clock or FakeClock(),
    )


def _force_measurement(service: COPService, data: COPInput) -> None:
    """Force a measurement by resetting the last measurement time."""
    service._last_measurement_time = 0.0
    service.update(data)


class TestCOPModeFiltering:
    """Tests for COP mode filtering via operation_mode."""

    def test_heating_mode_accumulates_only_during_heating(self):
        """COP heating sensor should only accumulate when operation_mode is 'heating'."""
        service = _build_service(expected_mode=MODE_HEATING)

        _force_measurement(service, _make_input(operation_mode=MODE_HEATING))
        assert service._accumulator.measurements, "Should accumulate during heating"

    def test_heating_mode_rejects_dhw(self):
        """COP heating sensor should NOT accumulate during DHW cycles."""
        service = _build_service(expected_mode=MODE_HEATING)

        _force_measurement(service, _make_input(operation_mode=MODE_DHW))
        assert not service._accumulator.measurements, "Should not accumulate during dhw"

    def test_dhw_mode_accumulates_only_during_dhw(self):
        """COP DHW sensor should only accumulate when operation_mode is 'dhw'."""
        service = _build_service(expected_mode=MODE_DHW)

        _force_measurement(service, _make_input(operation_mode=MODE_DHW))
        assert service._accumulator.measurements, "Should accumulate during dhw"

    def test_dhw_mode_rejects_heating(self):
        """COP DHW sensor should NOT accumulate during heating cycles."""
        service = _build_service(expected_mode=MODE_DHW)

        _force_measurement(service, _make_input(operation_mode=MODE_HEATING))
        assert not service._accumulator.measurements, (
            "Should not accumulate during heating"
        )

    def test_pool_mode_accumulates_only_during_pool(self):
        """COP pool sensor should only accumulate when operation_mode is 'pool'."""
        service = _build_service(expected_mode=MODE_POOL)

        _force_measurement(service, _make_input(operation_mode=MODE_POOL))
        assert service._accumulator.measurements, "Should accumulate during pool"

    def test_pool_mode_rejects_heating(self):
        """COP pool sensor should NOT accumulate during heating cycles."""
        service = _build_service(expected_mode=MODE_POOL)

        _force_measurement(service, _make_input(operation_mode=MODE_HEATING))
        assert not service._accumulator.measurements, (
            "Should not accumulate during heating"
        )

    def test_cooling_mode_accumulates_only_during_cooling(self):
        """COP cooling sensor should only accumulate when operation_mode is 'cooling'."""
        service = _build_service(expected_mode=MODE_COOLING)

        _force_measurement(service, _make_input(operation_mode=MODE_COOLING))
        assert service._accumulator.measurements, "Should accumulate during cooling"

    def test_cooling_mode_rejects_heating(self):
        """COP cooling sensor should NOT accumulate during heating cycles."""
        service = _build_service(expected_mode=MODE_COOLING)

        _force_measurement(service, _make_input(operation_mode=MODE_HEATING))
        assert not service._accumulator.measurements, (
            "Should not accumulate during heating"
        )

    def test_no_expected_mode_always_accumulates(self):
        """COP sensor with no expected_mode should always accumulate."""
        service = _build_service(expected_mode=None)

        _force_measurement(service, _make_input(operation_mode=MODE_HEATING))
        assert service._accumulator.measurements, (
            "Should accumulate with any operation_mode"
        )

    def test_no_expected_mode_accumulates_with_none_state(self):
        """COP sensor with no expected_mode should accumulate even with None operation_mode."""
        service = _build_service(expected_mode=None)

        _force_measurement(service, _make_input(operation_mode=None))
        assert service._accumulator.measurements, (
            "Should accumulate with None operation_mode"
        )

    def test_none_operation_mode_never_accumulates_when_mode_set(self):
        """When expected_mode is set, None operation_mode should prevent accumulation."""
        for mode in (MODE_HEATING, MODE_COOLING, MODE_DHW, MODE_POOL):
            service = _build_service(expected_mode=mode)

            _force_measurement(service, _make_input(operation_mode=None))
            assert not service._accumulator.measurements, (
                f"Should not accumulate with None operation_mode for mode={mode}"
            )


class TestCOPTransientNoneTimer:
    """Regression tests for issue #319.

    The measurement-interval timer must only advance once a complete, valid
    measurement is attempted, not on a transient None on a required sensor input.
    """

    def test_transient_none_does_not_block_next_valid_measurement(self):
        """A transient None must not consume the interval window.

        With the buggy ordering, the first (None) call advances the timer to
        ``now`` and the immediately following complete poll is rejected by the
        interval gate, dropping a valid measurement.
        """
        fixed_now = 10_000.0

        service = _build_service(expected_mode=None)
        # Open the gate: last measurement is older than the interval.
        service._last_measurement_time = fixed_now - COP_MEASUREMENTS_INTERVAL - 1

        # First poll: one required field missing, but compressor running + mode OK.
        service.update(_make_input(operation_mode=None, water_flow=None))
        assert not service._accumulator.measurements, (
            "Incomplete poll must not store a measurement"
        )

        # Second poll, same instant, fully valid: must be accepted.
        service.update(_make_input(operation_mode=None))
        assert service._accumulator.measurements, (
            "Valid poll following a transient None must be accepted"
        )

    def test_timer_not_advanced_on_invalid_input(self):
        """The interval timer must stay put when a required input is None."""
        fixed_now = 10_000.0

        service = _build_service(expected_mode=None)
        sentinel = fixed_now - COP_MEASUREMENTS_INTERVAL - 1
        service._last_measurement_time = sentinel

        service.update(_make_input(operation_mode=None, water_flow=None))

        assert service._last_measurement_time == sentinel, (
            "Timer must not advance on invalid (None) input"
        )

    def test_timer_advanced_on_valid_input(self):
        """The interval timer must advance exactly when a valid measurement is attempted."""
        fixed_now = 10_000.0

        service = _build_service(expected_mode=None)
        service._last_measurement_time = fixed_now - COP_MEASUREMENTS_INTERVAL - 1

        service.update(_make_input(operation_mode=None))

        assert service._last_measurement_time == fixed_now, (
            "Timer must advance to now when a valid measurement is attempted"
        )


class TestCOPReadTimeExpiry:
    """The COP verdict is a function of the stored samples *and* of now.

    Samples are only pruned when a new one is admitted. Once the compressor
    stops, no sample is admitted, so the verdict must expire at read time
    against the injected clock rather than wait for the next sample.
    """

    def _service_with_optimal_window(self) -> tuple[COPService, FakeClock]:
        clock = FakeClock()
        service = _build_service(expected_mode=None, clock=clock)
        for _ in range(20):
            # A flow that yields a plausible COP (~2.5), so a value is reported.
            service.update(_make_input(operation_mode=None, water_flow=500.0))
            clock.seconds += COP_MEASUREMENTS_INTERVAL
        assert service.get_quality().quality == "optimal"
        assert service.get_value() is not None
        return service, clock

    def test_quality_expires_without_new_samples(self):
        """Six hours after the last sample, nothing optimal is left to report."""
        service, clock = self._service_with_optimal_window()

        clock.seconds += 6 * 3600

        quality = service.get_quality()
        assert quality.quality == "no_data"
        assert quality.measurements == 0
        assert service.get_value() is None

    def test_window_slides_at_read_time(self):
        """Samples leave the window one by one as time passes, with no event."""
        service, clock = self._service_with_optimal_window()
        before = service.get_quality().measurements

        # 30-minute period: past 25 minutes, the oldest samples fall out.
        clock.seconds += 25 * 60

        after = service.get_quality()
        assert after.measurements < before
        assert after.quality != "optimal"

    def test_explicit_read_timestamp(self):
        """Replay-style use reads the verdict at an explicit instant."""
        service = _build_service(expected_mode=None)
        start = datetime(2026, 1, 1, 12, tzinfo=UTC)
        for minute in range(20):
            service.update(
                _make_input(operation_mode=None),
                timestamp=start + timedelta(minutes=minute),
            )
        end = start + timedelta(minutes=19)

        assert service.get_quality(timestamp=end).quality == "optimal"
        assert (
            service.get_quality(timestamp=end + timedelta(hours=6)).quality == "no_data"
        )
