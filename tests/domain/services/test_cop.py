"""Tests for COP domain service — mode filtering via operation_state."""

from custom_components.hitachi_yutaki.adapters.storage.in_memory import InMemoryStorage
from custom_components.hitachi_yutaki.domain.models.cop import (
    COPInput,
    PowerMeasurement,
)
from custom_components.hitachi_yutaki.domain.services.cop import (
    COP_MEASUREMENTS_HISTORY_SIZE,
    COP_MEASUREMENTS_PERIOD,
    COPService,
    EnergyAccumulator,
)


def _make_input(*, operation_state: str | None = None, hvac_action: str | None = None) -> COPInput:
    """Create a COPInput with valid sensor data and the given operation_state."""
    return COPInput(
        water_inlet_temp=30.0,
        water_outlet_temp=35.0,
        water_flow=15.0,
        compressor_current=5.0,
        compressor_frequency=50.0,
        hvac_action=hvac_action,
        operation_state=operation_state,
    )


def _build_service(*, expected_mode: str | None = None) -> COPService:
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
    )


def _force_measurement(service: COPService, data: COPInput) -> None:
    """Force a measurement by resetting the last measurement time."""
    service._last_measurement_time = 0.0
    service.update(data)


class TestCOPModeFiltering:
    """Tests for COP mode filtering via operation_state."""

    def test_heating_mode_accumulates_only_during_heating(self):
        """COP heating sensor should only accumulate when operation_state is 'heating'."""
        service = _build_service(expected_mode="heating")

        _force_measurement(service, _make_input(operation_state="heating"))
        assert service._accumulator.measurements, "Should accumulate during heating"

    def test_heating_mode_rejects_dhw(self):
        """COP heating sensor should NOT accumulate during DHW cycles."""
        service = _build_service(expected_mode="heating")

        _force_measurement(service, _make_input(operation_state="dhw"))
        assert not service._accumulator.measurements, "Should not accumulate during dhw"

    def test_dhw_mode_accumulates_only_during_dhw(self):
        """COP DHW sensor should only accumulate when operation_state is 'dhw'."""
        service = _build_service(expected_mode="dhw")

        _force_measurement(service, _make_input(operation_state="dhw"))
        assert service._accumulator.measurements, "Should accumulate during dhw"

    def test_dhw_mode_rejects_heating(self):
        """COP DHW sensor should NOT accumulate during heating cycles."""
        service = _build_service(expected_mode="dhw")

        _force_measurement(service, _make_input(operation_state="heating"))
        assert not service._accumulator.measurements, "Should not accumulate during heating"

    def test_pool_mode_accumulates_only_during_pool(self):
        """COP pool sensor should only accumulate when operation_state is 'pool'."""
        service = _build_service(expected_mode="pool")

        _force_measurement(service, _make_input(operation_state="pool"))
        assert service._accumulator.measurements, "Should accumulate during pool"

    def test_pool_mode_rejects_heating(self):
        """COP pool sensor should NOT accumulate during heating cycles."""
        service = _build_service(expected_mode="pool")

        _force_measurement(service, _make_input(operation_state="heating"))
        assert not service._accumulator.measurements, "Should not accumulate during heating"

    def test_cooling_mode_accumulates_only_during_cooling(self):
        """COP cooling sensor should only accumulate when operation_state is 'cooling'."""
        service = _build_service(expected_mode="cooling")

        _force_measurement(service, _make_input(operation_state="cooling"))
        assert service._accumulator.measurements, "Should accumulate during cooling"

    def test_cooling_mode_rejects_heating(self):
        """COP cooling sensor should NOT accumulate during heating cycles."""
        service = _build_service(expected_mode="cooling")

        _force_measurement(service, _make_input(operation_state="heating"))
        assert not service._accumulator.measurements, "Should not accumulate during heating"

    def test_no_expected_mode_always_accumulates(self):
        """COP sensor with no expected_mode should always accumulate."""
        service = _build_service(expected_mode=None)

        _force_measurement(service, _make_input(operation_state="heating"))
        assert service._accumulator.measurements, "Should accumulate with any operation_state"

    def test_no_expected_mode_accumulates_with_none_state(self):
        """COP sensor with no expected_mode should accumulate even with None operation_state."""
        service = _build_service(expected_mode=None)

        _force_measurement(service, _make_input(operation_state=None))
        assert service._accumulator.measurements, "Should accumulate with None operation_state"

    def test_none_operation_state_never_accumulates_when_mode_set(self):
        """When expected_mode is set, None operation_state should prevent accumulation."""
        for mode in ("heating", "cooling", "dhw", "pool"):
            service = _build_service(expected_mode=mode)

            _force_measurement(service, _make_input(operation_state=None))
            assert not service._accumulator.measurements, (
                f"Should not accumulate with None operation_state for mode={mode}"
            )
