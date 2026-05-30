"""Helpers to rebuild domain storages from Home Assistant Recorder history."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging

from homeassistant.components.recorder import get_instance, history
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import PowerConverter

from ...domain.models.cop import PowerMeasurement
from ...domain.models.electrical import ElectricalPowerInput
from ...domain.services.electrical import calculate_electrical_power

_LOGGER = logging.getLogger(__name__)

ThermalCalculator = Callable[[float, float, float], float]
ElectricalCalculator = Callable[[float], float]


async def async_replay_cop_history(
    hass: HomeAssistant,
    *,
    entity_ids: dict[str, str],
    thermal_calculator: ThermalCalculator,
    electrical_calculator: ElectricalCalculator | None = None,
    window: timedelta,
    measurement_interval: int,
    max_measurements: int,
    accepted_operation_states: set[str] | None = None,
    is_three_phase: bool = False,
) -> list[PowerMeasurement]:
    """Reconstruct power measurements from Recorder sensor history.

    Electrical power is rebuilt per replayed point from that point's *historical*
    data (issue #316): when a whole-unit power meter is configured its value is
    looked up under the ``power_entity`` / ``measured_power`` key for the matching
    timestamp; otherwise an I×U estimate is computed from the historical current
    (and historical voltage when available). The live ``electrical_calculator`` is
    intentionally NOT used here — reusing it would stamp the single instantaneous
    live power reading onto every replayed point.

    ``electrical_calculator`` is accepted for backward compatibility but ignored.
    """
    if electrical_calculator is not None:
        _LOGGER.debug(
            "async_replay_cop_history ignores the live electrical_calculator; "
            "electrical power is reconstructed per-point from history (#316)"
        )
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
        elif key == "power_entity":
            # Whole-unit power meter: normalise each historical reading to kW
            # using its own unit_of_measurement and store under "measured_power".
            for state in states:
                parsed = _parse_power_kw(state)
                if parsed is None:
                    continue
                timeline.append(
                    (
                        _as_local_naive(state.last_changed or state.last_updated),
                        "measured_power",
                        parsed,
                    )
                )
        elif key == "voltage_entity":
            for state in states:
                parsed = _parse_float(state)
                if parsed is None:
                    continue
                timeline.append(
                    (
                        _as_local_naive(state.last_changed or state.last_updated),
                        "voltage",
                        parsed,
                    )
                )
        else:
            parser = _parse_bool if key.endswith("_running") else _parse_float
            for state in states:
                parsed = parser(state)
                if parsed is None:
                    continue
                timeline.append(
                    (
                        _as_local_naive(state.last_changed or state.last_updated),
                        key,
                        parsed,
                    )
                )

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
            is_three_phase=is_three_phase,
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
    *,
    is_three_phase: bool = False,
) -> PowerMeasurement | None:
    """Build a single COP measurement from the per-point historical snapshot.

    Electrical power is reconstructed from this point's own historical values
    (issue #316): a whole-unit power meter reading wins (``measured_power``,
    already in kW); otherwise an I×U estimate is computed from the summed
    historical compressor currents and the historical (or default) voltage.
    """
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

    measured_power = latest.get("measured_power")
    voltage = latest.get("voltage")

    # Sum compressor currents (S80) so a single calculation covers the whole
    # unit. For the measured_power path the current is ignored anyway; for the
    # I×U path U×(I1+I2) == U×I1 + U×I2.
    total_current = compressor_current
    secondary_frequency = latest.get("secondary_compressor_frequency")
    secondary_current = latest.get("secondary_compressor_current")
    if secondary_frequency and secondary_frequency > 0 and secondary_current:
        total_current += secondary_current

    electrical_power = calculate_electrical_power(
        ElectricalPowerInput(
            current=total_current,
            measured_power=measured_power,
            voltage=voltage,
            is_three_phase=is_three_phase,
        )
    )
    if electrical_power <= 0:
        return None

    return PowerMeasurement(timestamp, thermal_power, electrical_power)


def _parse_float(state: State) -> float | None:
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _parse_power_kw(state: State) -> float | None:
    """Parse a power-meter state and normalise it to kW via its unit attribute."""
    value = _parse_float(state)
    if value is None:
        return None
    from_unit = state.attributes.get("unit_of_measurement")
    if from_unit is None:
        return None
    try:
        return PowerConverter.convert(value, from_unit, UnitOfPower.KILO_WATT)
    except (ValueError, KeyError):
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
