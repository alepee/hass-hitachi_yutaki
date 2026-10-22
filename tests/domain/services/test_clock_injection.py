"""Clock regressions: elapsed durations must not follow civil-clock corrections."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.hitachi_yutaki.adapters.storage.in_memory import InMemoryStorage
from custom_components.hitachi_yutaki.domain.models.cop import (
    COPInput,
    PowerMeasurement,
)
from custom_components.hitachi_yutaki.domain.models.cycling import CyclingInput
from custom_components.hitachi_yutaki.domain.models.refrigerant import RefrigerantInput
from custom_components.hitachi_yutaki.domain.services.cop import (
    COPService,
    EnergyAccumulator,
)
from custom_components.hitachi_yutaki.domain.services.cycling import CyclingMonitor
from custom_components.hitachi_yutaki.domain.services.defrost_guard import DefrostGuard
from custom_components.hitachi_yutaki.domain.services.refrigerant import (
    RefrigerantMonitor,
)
from custom_components.hitachi_yutaki.domain.services.thermal.accumulator import (
    ThermalEnergyAccumulator,
)
from custom_components.hitachi_yutaki.domain.services.timing import CompressorHistory


@pytest.mark.parametrize("existing", [True, False])
def test_cop_rejects_mixed_timestamp_history_atomically(clock, existing):
    """Invalid replay inputs never leave the COP buffer partly overwritten."""
    accumulator = EnergyAccumulator(
        InMemoryStorage(max_len=10), timedelta(minutes=30), clock=clock
    )
    if existing:
        accumulator.add_measurement(5, 2)
    before = accumulator.measurements
    incoming = [PowerMeasurement(clock.wall.replace(tzinfo=None), 6, 2)]
    if not existing:
        incoming.insert(0, PowerMeasurement(clock.wall, 5, 2))
    with pytest.raises(ValueError, match="timezone awareness"):
        accumulator.bulk_load(incoming)
    assert accumulator.measurements == before


@pytest.mark.parametrize("existing", [True, False])
def test_timing_rejects_mixed_timestamp_history_atomically(clock, existing):
    """Invalid replay timestamps do not add transitions or partial history."""
    storage = InMemoryStorage(max_len=10)
    history = CompressorHistory(storage, max_history=10, clock=clock)
    if existing:
        history.add_state(False)
    before = storage.get_all()
    incoming = [(clock.wall.replace(tzinfo=None), True)]
    if not existing:
        incoming.insert(0, (clock.wall, False))
    with pytest.raises(ValueError, match="timezone awareness"):
        history.bulk_load(incoming)
    assert storage.get_all() == before
    assert history.get_average_times() == (None, None, None)


def test_thermal_backward_elapsed_time_never_subtracts_energy(clock):
    """The reported 100 -> 90 seconds at 10 kW no longer adds -0.027778 kWh."""
    accumulator = ThermalEnergyAccumulator(clock=clock)
    clock.seconds = 100
    accumulator.update(10, 0, True)
    clock.seconds = 90
    accumulator.update(10, 0, True)
    assert accumulator.total_heating_energy == 0
    assert accumulator.daily_heating_energy == 0


def test_thermal_midnight_uses_local_date_but_monotonic_duration(clock):
    """Cross local midnight with only ten elapsed seconds and retain total energy."""
    clock.wall = datetime(2026, 1, 1, 23, 59, 55, tzinfo=ZoneInfo("Asia/Tokyo"))
    clock.seconds = 0
    accumulator = ThermalEnergyAccumulator(
        initial_daily_heating=2, initial_total_heating=20, clock=clock
    )
    accumulator.update(10, 0, True)
    clock.seconds = 10
    clock.wall += timedelta(seconds=10)
    accumulator.update(10, 0, True)
    assert accumulator.last_reset_date == clock.wall.date()
    assert accumulator.daily_heating_energy == pytest.approx(10 / 360)
    assert accumulator.total_heating_energy == pytest.approx(20 + 10 / 360)


def test_timing_uses_monotonic_duration_across_wall_clock_rollback(clock):
    """An hour of civil-clock rollback cannot erase a real ten-minute run."""
    history = CompressorHistory(InMemoryStorage(), 10, clock=clock)
    history.add_state(True)
    clock.seconds += 600
    clock.wall -= timedelta(hours=1)
    history.add_state(False)
    assert history.get_average_times()[1] == 10


def test_timing_replay_preserves_dst_offsets():
    """The repeated local hour during DST is still ten real minutes."""
    zone = ZoneInfo("Europe/Paris")
    history = CompressorHistory(InMemoryStorage(), 10)
    history.add_state(True, datetime(2026, 10, 25, 2, 55, tzinfo=zone, fold=0))
    history.add_state(False, datetime(2026, 10, 25, 2, 5, tzinfo=zone, fold=1))
    assert history.get_average_times()[1] == 10


def test_cop_interval_and_integration_ignore_wall_clock_rollback(clock):
    """Live samples remain one minute apart after a civil-clock correction."""
    accumulator = EnergyAccumulator(InMemoryStorage(), timedelta(minutes=30))
    service = COPService(accumulator, lambda *_: 6, lambda _: 2, clock=clock)
    data = COPInput(30, 35, 1, 0, 50, electrical_power=2)
    service.update(data)
    clock.wall -= timedelta(hours=1)
    clock.seconds += 60
    service.update(data)
    assert service.get_value() == 3
    assert service.get_quality().time_span_minutes == 1


def test_defrost_recovery_timeout_uses_monotonic_clock(clock):
    """A civil jump cannot finish recovery early or extend it."""
    guard = DefrostGuard(clock=clock)
    guard.update(True, None)
    guard.update(False, None)
    clock.wall += timedelta(days=2)
    clock.seconds += 299
    guard.update(False, None)
    assert not guard.is_data_reliable
    clock.seconds += 1
    guard.update(False, None)
    assert guard.is_data_reliable


def test_refrigerant_replay_throttles_on_explicit_timestamps():
    """Repeated or nearby replay points cannot qualify a whole day's samples."""
    monitor = RefrigerantMonitor(InMemoryStorage(), (-10, 80))
    data = RefrigerantInput("heating", 50, 40, -5, 40, 7, True)
    timestamp = datetime(2026, 1, 1, 12, tzinfo=UTC)
    for seconds in (0, 0, 10, 59, 60, 61, 120):
        monitor.update(data, timestamp=timestamp + timedelta(seconds=seconds))
    assert monitor.get_status().today_samples == 3


def test_refrigerant_live_throttle_ignores_civil_correction(clock):
    """Live sampling uses monotonic seconds, with a separately controlled date."""
    monitor = RefrigerantMonitor(InMemoryStorage(), (-10, 80), clock=clock)
    data = RefrigerantInput("heating", 50, 40, -5, 40, 7, True)
    monitor.update(data)
    clock.wall -= timedelta(hours=1)
    clock.seconds += 60
    monitor.update(data)
    assert monitor.get_status().today_samples == 2


def test_cycling_debounce_and_run_duration_ignore_wall_clock_rollback(clock):
    """Thirty-second debounce and cycle periods run on the monotonic timeline."""
    monitor = CyclingMonitor(InMemoryStorage(), clock=clock)
    monitor.update(CyclingInput("heating", False, True))
    for seconds, running in ((5, True), (35, True), (65, False), (95, False)):
        clock.seconds = 10000 + seconds
        clock.wall = datetime(2026, 1, 1, 11, tzinfo=UTC)
        monitor.update(CyclingInput("heating", running, True))
    assert monitor.get_status().median_run_today == 1


def test_services_require_time_dependency():
    """An omitted clock cannot silently fall back to real wall time."""
    with pytest.raises(ValueError, match="clock or explicit timestamp"):
        DefrostGuard().update(False, 5)
    with pytest.raises(ValueError, match="clock or explicit timestamp"):
        CompressorHistory(InMemoryStorage(), 10).add_state(True)
