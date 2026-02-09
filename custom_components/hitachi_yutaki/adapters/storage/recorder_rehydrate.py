"""Helpers to rebuild domain storages from Home Assistant Recorder history."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging

from homeassistant.components.recorder import get_instance, history
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from ...domain.models.cop import PowerMeasurement

_LOGGER = logging.getLogger(__name__)

ThermalCalculator = Callable[[float, float, float], float]
ElectricalCalculator = Callable[[float], float]


async def async_replay_cop_history(
    hass: HomeAssistant,
    *,
    entity_ids: dict[str, str],
    thermal_calculator: ThermalCalculator,
    electrical_calculator: ElectricalCalculator,
    window: timedelta,
    measurement_interval: int,
    max_measurements: int,
    accepted_operation_states: set[str] | None = None,
) -> list[PowerMeasurement]:
    """Reconstruct power measurements from Recorder sensor history."""
    required_keys = {
        "water_inlet_temp",
        "water_outlet_temp",
        "water_flow",
        "compressor_current",
        "compressor_frequency",
    }
    if not required_keys.issubset(entity_ids):
        missing = required_keys.difference(entity_ids)
        _LOGGER.debug("COP history replay skipped, missing entities: %s", missing)
        return []

    states_map = await _async_fetch_history(
        hass, list(entity_ids.values()), window, include_start_state=True
    )
    if not states_map:
        return []

    timeline: list[tuple[datetime, str, float | str]] = []
    for key, entity_id in entity_ids.items():
        states = states_map.get(entity_id)
        if not states:
            continue
        if key == "operation_state":
            timeline.extend(
                (
                    _as_local_naive(state.last_changed or state.last_updated),
                    key,
                    state.state,
                )
                for state in states
                if state.state not in (None, "unknown", "unavailable")
            )
        else:
            parser = _parse_bool if key.endswith("_running") else _parse_float
            for state in states:
                parsed = parser(state)
                if parsed is None:
                    continue
                timeline.append((
                    _as_local_naive(state.last_changed or state.last_updated),
                    key,
                    parsed,
                ))

    if not timeline:
        return []

    timeline.sort(key=lambda item: item[0])
    latest: dict[str, float | str] = {}
    last_measurement: datetime | None = None
    measurements: list[PowerMeasurement] = []

    for timestamp, key, value in timeline:
        latest[key] = value
        if not required_keys.issubset(latest):
            continue
        if latest["compressor_frequency"] <= 0 or latest["compressor_current"] <= 0:
            continue
        # Filter by operation_state when mode filtering is requested
        if accepted_operation_states is not None:
            current_op_state = latest.get("operation_state")
            if current_op_state not in accepted_operation_states:
                continue
        if (
            last_measurement
            and (timestamp - last_measurement).total_seconds() < measurement_interval
        ):
            continue

        measurement = _build_power_measurement(
            timestamp,
            latest,
            thermal_calculator,
            electrical_calculator,
        )
        if measurement is None:
            continue
        measurements.append(measurement)
        last_measurement = timestamp

    if len(measurements) > max_measurements:
        measurements = measurements[-max_measurements:]

    return measurements


async def async_replay_compressor_states(
    hass: HomeAssistant,
    *,
    entity_id: str,
    window: timedelta,
    max_states: int,
) -> list[tuple[datetime, bool]]:
    """Reconstruct compressor running history from Recorder binary sensor data."""
    states_map = await _async_fetch_history(
        hass, [entity_id], window, include_start_state=True
    )
    if not states_map or entity_id not in states_map:
        return []

    entries: list[tuple[datetime, bool]] = []
    for state in states_map[entity_id]:
        parsed = _parse_bool(state)
        if parsed is None:
            continue
        timestamp = _as_local_naive(state.last_changed or state.last_updated)
        entries.append((timestamp, bool(parsed)))

    if len(entries) > max_states:
        entries = entries[-max_states:]

    return entries


def _build_power_measurement(
    timestamp: datetime,
    latest: dict[str, float],
    thermal_calculator: ThermalCalculator,
    electrical_calculator: ElectricalCalculator,
) -> PowerMeasurement | None:
    try:
        water_inlet = latest["water_inlet_temp"]
        water_outlet = latest["water_outlet_temp"]
        water_flow = latest["water_flow"]
        compressor_current = latest["compressor_current"]
    except KeyError:
        return None

    thermal_power = thermal_calculator(water_inlet, water_outlet, water_flow)
    if thermal_power <= 0:
        return None

    electrical_power = electrical_calculator(compressor_current)
    if electrical_power <= 0:
        return None

    secondary_frequency = latest.get("secondary_compressor_frequency")
    secondary_current = latest.get("secondary_compressor_current")
    if secondary_frequency and secondary_frequency > 0 and secondary_current:
        additional = electrical_calculator(secondary_current)
        if additional > 0:
            electrical_power += additional

    if electrical_power <= 0:
        return None

    return PowerMeasurement(timestamp, thermal_power, electrical_power)


def _parse_float(state: State) -> float | None:
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _parse_bool(state: State) -> bool | None:
    if state.state in ("on", "off"):
        return state.state == "on"
    if state.state in ("True", "False"):
        return state.state == "True"
    return None


async def _async_fetch_history(
    hass: HomeAssistant,
    entity_ids: list[str],
    window: timedelta,
    *,
    include_start_state: bool,
) -> dict[str, list[State]]:
    if not entity_ids:
        return {}

    start_time = dt_util.utcnow() - window

    def _get_states() -> dict[str, list[State]]:
        return history.get_significant_states(
            hass,
            start_time,
            None,
            entity_ids,
            include_start_time_state=include_start_state,
            significant_changes_only=False,
        )

    try:
        return await get_instance(hass).async_add_executor_job(_get_states)
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Recorder history unavailable for entities: %s", entity_ids)
        return {}


def _as_local_naive(timestamp: datetime | None) -> datetime:
    ts = timestamp or dt_util.utcnow()
    return dt_util.as_local(ts).replace(tzinfo=None)
