"""Tests for the per-cycle heat balance behind the short-cycling alert (#512)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from custom_components.hitachi_yutaki.adapters.storage.in_memory import InMemoryStorage
from custom_components.hitachi_yutaki.domain.models.cycling import (
    CyclingDiagnosis,
    CyclingInput,
    CyclingStatus,
)
from custom_components.hitachi_yutaki.domain.services.cycling import (
    HISTORY_DAYS,
    STATUS_ALERT,
    CyclingMonitor,
)
from custom_components.hitachi_yutaki.domain.services.cycling_diagnosis import (
    C_WATER_J_PER_KG_K,
    KW_PER_M3H_K,
    CycleSample,
    DailyCycleLog,
    combine_diagnoses,
    measure_cycle,
)
from custom_components.hitachi_yutaki.domain.services.maintenance import (
    CYCLING_ADVICE_CASCADE,
    CYCLING_ADVICE_DIAGNOSED,
    CYCLING_ADVICE_GENERIC,
    cycling_advice,
)

START = datetime(2026, 1, 5, 6, 0, 0)
POLL_S = 5.0

# A simulated installation: a unit producing OUTPUT_KW into a loop of VOLUME_L
# whose emitters absorb LOAD_KW, stopping when the outlet reaches TARGET_C and
# restarting once it has fallen by SWING_K.
OUTPUT_KW = 6.0
LOAD_KW = 3.0
VOLUME_L = 60.0
TARGET_C = 35.0
SWING_K = 3.0
FLOW_M3H = 1.0


def _monitor() -> CyclingMonitor:
    return CyclingMonitor(InMemoryStorage(max_len=HISTORY_DAYS))


def _simulate(
    monitor: CyclingMonitor,
    *,
    start: datetime,
    cycles: int,
    thermo_off: bool = True,
    flow: float | None = FLOW_M3H,
    secondary: bool | None = None,
    defrost_in_cycle: int | None = None,
) -> datetime:
    """Feed physically consistent heating cycles, polling every 5 seconds."""
    heat_capacity = C_WATER_J_PER_KG_K * VOLUME_L  # J/K
    rise = (OUTPUT_KW - LOAD_KW) * 1000 / heat_capacity  # K/s while running
    fall = LOAD_KW * 1000 / heat_capacity  # K/s while resting
    delta_t = OUTPUT_KW / (KW_PER_M3H_K * FLOW_M3H)

    now = start
    outlet = TARGET_C - SWING_K
    for index in range(cycles):
        while outlet < TARGET_C:
            monitor.update(
                CyclingInput(
                    operation_mode="heating",
                    compressor_running=True,
                    data_reliable=index != defrost_in_cycle,
                    thermo_off=False,
                    water_inlet_temp=outlet - delta_t,
                    water_outlet_temp=outlet,
                    water_target_temp=TARGET_C,
                    water_flow=flow,
                    compressor_frequency=31.0,
                    secondary_compressor_running=secondary,
                ),
                timestamp=now,
            )
            outlet += rise * POLL_S
            now += timedelta(seconds=POLL_S)
        while outlet > TARGET_C - SWING_K:
            monitor.update(
                CyclingInput(
                    operation_mode="heating",
                    compressor_running=False,
                    thermo_off=thermo_off,
                    water_inlet_temp=outlet,
                    water_outlet_temp=outlet,
                    water_target_temp=TARGET_C,
                    water_flow=flow,
                    compressor_frequency=0.0,
                    secondary_compressor_running=False if secondary else None,
                ),
                timestamp=now,
            )
            outlet -= fall * POLL_S
            now += timedelta(seconds=POLL_S)
    return now


def _next_day(monitor: CyclingMonitor, after: datetime) -> datetime:
    """Flush the running day."""
    next_day = datetime.combine(
        (after + timedelta(days=1)).date(), datetime.min.time()
    ) + timedelta(hours=6)
    monitor.update(
        CyclingInput(operation_mode="heating", compressor_running=False),
        timestamp=next_day,
    )
    return next_day


def test_heat_balance_recovers_the_simulated_installation() -> None:
    """Output, absorbed heat and loop volume come back from the water signals."""
    monitor = _monitor()
    now = _simulate(monitor, start=START, cycles=20)
    _next_day(monitor, now)

    status = monitor.get_status()
    diagnosis = status.diagnosis
    assert diagnosis is not None
    assert status.diagnosis_days == 1
    assert diagnosis.output_kw == pytest.approx(OUTPUT_KW, rel=0.02)
    assert diagnosis.absorbed_kw == pytest.approx(LOAD_KW, rel=0.05)
    assert diagnosis.load_ratio == pytest.approx(0.5, abs=0.03)
    assert diagnosis.loop_volume_l == pytest.approx(VOLUME_L, rel=0.07)
    assert diagnosis.floor_share == 1.0
    assert diagnosis.return_minus_target_k == pytest.approx(0.0, abs=0.1)
    assert diagnosis.secondary_share is None


def test_stops_decided_by_a_room_thermostat_are_not_measured() -> None:
    """A demand-off stop does not saturate the loop: no heat balance."""
    monitor = _monitor()
    now = _simulate(monitor, start=START, cycles=20, thermo_off=False)
    _next_day(monitor, now)

    status = monitor.get_status()
    assert status.valid_days == 1  # the cycles still count for the verdict
    assert status.diagnosis is None


def test_no_flow_reading_means_no_diagnosis() -> None:
    """Without a flow reading the output is unknown and nothing is derived."""
    monitor = _monitor()
    now = _simulate(monitor, start=START, cycles=20, flow=None)
    _next_day(monitor, now)

    assert monitor.get_status().diagnosis is None


def test_defrost_discards_the_cycle_in_progress() -> None:
    """A defrost breaks the cycle chain, so the cycle around it is not measured."""
    clean = _monitor()
    _next_day(clean, _simulate(clean, start=START, cycles=10))
    broken = _monitor()
    _next_day(broken, _simulate(broken, start=START, cycles=10, defrost_in_cycle=4))

    clean_cycles = clean.get_status().diagnosis.cycles
    broken_cycles = broken.get_status().diagnosis.cycles
    assert broken_cycles < clean_cycles


def test_secondary_compressor_share_is_measured() -> None:
    """On a cascade unit the share of run time with both compressors is kept."""
    monitor = _monitor()
    _next_day(monitor, _simulate(monitor, start=START, cycles=20, secondary=True))

    diagnosis = monitor.get_status().diagnosis
    assert diagnosis.secondary_share == 1.0
    assert diagnosis.secondary_target_c == TARGET_C


def test_diagnosis_survives_a_restart() -> None:
    """The daily heat balance is persisted with the aggregate."""
    monitor = _monitor()
    _next_day(monitor, _simulate(monitor, start=START, cycles=20))
    snapshot = monitor.serialize()

    restored = _monitor()
    restored.restore(snapshot)

    assert restored.get_status().diagnosis == monitor.get_status().diagnosis


def test_snapshot_without_diagnosis_still_restores() -> None:
    """Aggregates stored before #512 carry no diagnosis and load unchanged."""
    monitor = _monitor()
    monitor.restore(
        {
            "alert_streak": 0,
            "aggregates": [
                {
                    "day": "2026-01-04",
                    "cycles": 30,
                    "median_period": 9.0,
                    "peak_starts": 7,
                    "median_run": 4.0,
                    "faulted": True,
                }
            ],
        }
    )
    status = monitor.get_status()
    assert status.valid_days == 1
    assert status.diagnosis is None


def test_malformed_diagnosis_is_rejected() -> None:
    """A corrupt diagnosis fails validation like any other malformed snapshot."""
    monitor = _monitor()
    with pytest.raises(ValueError):
        monitor.restore(
            {
                "aggregates": [
                    {
                        "day": "2026-01-04",
                        "cycles": 30,
                        "median_period": 9.0,
                        "peak_starts": 7,
                        "median_run": 4.0,
                        "faulted": True,
                        "diagnosis": {"cycles": 4},
                    }
                ]
            }
        )


def test_alert_diagnosis_prefers_faulted_days() -> None:
    """The advice describes the days that cycled, not the quiet ones."""
    days = [
        CyclingDiagnosis(
            cycles=10,
            output_kw=6.0,
            absorbed_kw=absorbed,
            load_ratio=absorbed / 6.0,
            loop_volume_l=60.0,
            run_min=5.0,
            rest_min=5.0,
            swing_k=3.0,
            floor_share=1.0,
            return_minus_target_k=0.0,
            secondary_share=None,
            secondary_target_c=None,
        )
        for absorbed in (3.0, 3.2, 5.5)
    ]
    combined = combine_diagnoses(days)
    assert combined is not None
    assert combined.absorbed_kw == 3.2
    assert combined.cycles == 30


def _sample(outlet: float, *, inlet: float | None = None) -> CycleSample:
    return CycleSample(
        inlet=inlet,
        outlet=outlet,
        target=35.0,
        flow=1.0,
        frequency=31.0,
        secondary_running=None,
    )


def test_short_phases_and_flat_swings_are_not_measured() -> None:
    """A swing within the register resolution or a phase under a minute is noise."""
    run = [_sample(35.0, inlet=30.0)] * 12
    rest = [_sample(34.5)] * 12
    assert measure_cycle(run, rest, run_s=300, rest_s=300, stop=None) is None
    rest = [_sample(32.0)] * 12
    assert measure_cycle(run, rest, run_s=30, rest_s=300, stop=None) is None
    assert measure_cycle(run, rest, run_s=300, rest_s=300, stop=None) is not None


def test_frequency_floor_ignores_ramp_samples() -> None:
    """Ramp samples below the plateau do not move the floor off the plateau."""
    log = DailyCycleLog()
    log.frequencies = [24.0, 26.0, 28.0, 30.0] * 5 + [31.0] * 60 + [50.0] * 20
    for _ in range(4):
        log.cycles.append(
            measure_cycle(
                [_sample(35.0, inlet=30.0)] * 12,
                [_sample(32.0)] * 12,
                run_s=300,
                rest_s=300,
                stop=None,
            )
        )
    diagnosis = log.diagnose()
    assert diagnosis is not None
    assert diagnosis.floor_share == pytest.approx(0.8)


_DIAGNOSIS = CyclingDiagnosis(
    cycles=120,
    output_kw=5.9,
    absorbed_kw=3.04,
    load_ratio=0.515,
    loop_volume_l=89.6,
    run_min=6.6,
    rest_min=4.0,
    swing_k=3.0,
    floor_share=1.0,
    return_minus_target_k=0.0,
    secondary_share=None,
    secondary_target_c=None,
)
_ALERT = CyclingStatus(
    status=STATUS_ALERT,
    cycles_today=40,
    peak_starts_today=8,
    median_period_today=10.0,
    median_run_today=6.6,
    valid_days=7,
    alert_streak=5,
    diagnosis=_DIAGNOSIS,
    diagnosis_days=5,
)


def test_advice_is_generic_without_a_heat_balance() -> None:
    """No flow reading: the generic list of causes."""
    assert cycling_advice(replace(_ALERT, diagnosis=None)) == (
        CYCLING_ADVICE_GENERIC,
        {},
    )
    assert cycling_advice(None) == (CYCLING_ADVICE_GENERIC, {})


def test_advice_quotes_the_installation_numbers() -> None:
    """The tailored text carries the unit's own output, load and volume."""
    variant, placeholders = cycling_advice(_ALERT)
    assert variant == CYCLING_ADVICE_DIAGNOSED
    assert placeholders == {
        "days": "5",
        "output_kw": "5.9",
        "absorbed_kw": "3.0",
        "load_pct": "52",
        "volume_l": "90",
        "run_min": "6.6",
        "rest_min": "4.0",
        "floor_pct": "100",
    }


@pytest.mark.parametrize(
    ("share", "expected"),
    [(0.1, CYCLING_ADVICE_DIAGNOSED), (0.35, CYCLING_ADVICE_CASCADE)],
)
def test_cascade_hint_needs_the_secondary_compressor_to_run(
    share: float, expected: str
) -> None:
    """The cascade hint only shows when the second compressor really runs."""
    status = replace(
        _ALERT,
        diagnosis=replace(_DIAGNOSIS, secondary_share=share, secondary_target_c=45.5),
    )
    variant, placeholders = cycling_advice(status)
    assert variant == expected
    if expected == CYCLING_ADVICE_CASCADE:
        assert placeholders["secondary_pct"] == "35"
        assert placeholders["secondary_target"] == "46"
