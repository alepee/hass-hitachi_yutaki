"""Telemetry collector — extracts metrics from coordinator data into a circular buffer."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
import logging
from typing import Any

from .models import MetricPoint, TelemetryLevel

_LOGGER = logging.getLogger(__name__)

# Default buffer size: 360 points = 30 minutes at 5s poll interval
DEFAULT_BUFFER_MAX_SIZE = 360

# Coordinator data key → unit_mode string mapping
_UNIT_MODE_MAP = {0: "cool", 1: "heat", 2: "auto"}


class TelemetryCollector:
    """Collects telemetry metrics from coordinator data into a circular buffer.

    When the buffer is full, oldest points are dropped (deque maxlen).
    Call flush() to retrieve and clear all buffered points.
    """

    def __init__(
        self,
        level: TelemetryLevel,
        buffer_max_size: int = DEFAULT_BUFFER_MAX_SIZE,
    ) -> None:
        """Initialize the collector."""
        self._level = level
        self._buffer: deque[MetricPoint] = deque(maxlen=buffer_max_size)

    @property
    def level(self) -> TelemetryLevel:
        """Return the current telemetry level."""
        return self._level

    @property
    def buffer_size(self) -> int:
        """Return the current number of buffered points."""
        return len(self._buffer)

    def collect(
        self,
        data: dict[str, Any],
        is_compressor_running: bool | None = None,
        is_defrosting: bool | None = None,
    ) -> None:
        """Extract metrics from coordinator data and add to the buffer.

        Collects when level is BASIC or FULL (skips OFF).
        Basic level accumulates points for daily aggregation.
        Full level accumulates points for 5-minute metric batches.

        Args:
            data: The coordinator data dict (raw Modbus values).
            is_compressor_running: From api_client.is_compressor_running.
            is_defrosting: From api_client.is_defrosting.

        """
        if self._level == TelemetryLevel.OFF:
            return

        if not data or not data.get("is_available"):
            return

        now = datetime.now(tz=UTC)

        # Map unit_mode integer to string
        unit_mode_raw = data.get("unit_mode")
        unit_mode = (
            _UNIT_MODE_MAP.get(unit_mode_raw) if unit_mode_raw is not None else None
        )

        # Detect DHW active from operation_state
        operation_state = data.get("operation_state")
        dhw_active = (
            operation_state == "operation_state_dhw_on" if operation_state else None
        )

        point = MetricPoint(
            time=now,
            outdoor_temp=_to_float(data.get("outdoor_temp")),
            water_inlet_temp=_to_float(data.get("water_inlet_temp")),
            water_outlet_temp=_to_float(data.get("water_outlet_temp")),
            dhw_temp=_to_float(data.get("dhw_current_temp")),
            compressor_on=is_compressor_running,
            compressor_frequency=_to_float(data.get("compressor_frequency")),
            compressor_current=_to_float(data.get("compressor_current")),
            thermal_power=_to_float(data.get("thermal_power")),
            electrical_power=_to_float(data.get("power_consumption")),
            cop_instant=_to_float(data.get("cop_instant")),
            cop_quality=data.get("cop_quality"),
            unit_mode=unit_mode,
            is_defrosting=is_defrosting,
            dhw_active=dhw_active,
            circuit1_water_temp=_to_float(data.get("circuit1_current_temp")),
            circuit2_water_temp=_to_float(data.get("circuit2_current_temp")),
            # Setpoints and control state
            circuit1_target_temp=_to_float(data.get("circuit1_target_temp")),
            circuit2_target_temp=_to_float(data.get("circuit2_target_temp")),
            dhw_target_temp=_to_float(data.get("dhw_target_temp")),
            water_target_temp=_to_float(data.get("water_target_temp")),
            water_flow=_to_float(data.get("water_flow")),
            circuit1_otc_method_heating=data.get(
                "circuit1_otc_calculation_method_heating"
            ),
            circuit1_otc_method_cooling=data.get(
                "circuit1_otc_calculation_method_cooling"
            ),
            circuit2_otc_method_heating=data.get(
                "circuit2_otc_calculation_method_heating"
            ),
            circuit2_otc_method_cooling=data.get(
                "circuit2_otc_calculation_method_cooling"
            ),
            circuit1_eco_mode=_to_bool(data.get("circuit1_eco_mode")),
            circuit2_eco_mode=_to_bool(data.get("circuit2_eco_mode")),
            circuit1_power=_to_bool(data.get("circuit1_power")),
            circuit2_power=_to_bool(data.get("circuit2_power")),
            dhw_power=_to_bool(data.get("dhw_power")),
            # OTC parameters
            circuit1_max_flow_temp_heating=_to_float(
                data.get("circuit1_max_flow_temp_heating_otc")
            ),
            circuit1_max_flow_temp_cooling=_to_float(
                data.get("circuit1_max_flow_temp_cooling_otc")
            ),
            circuit1_heat_eco_offset=_to_float(data.get("circuit1_heat_eco_offset")),
            circuit1_cool_eco_offset=_to_float(data.get("circuit1_cool_eco_offset")),
            circuit2_max_flow_temp_heating=_to_float(
                data.get("circuit2_max_flow_temp_heating_otc")
            ),
            circuit2_max_flow_temp_cooling=_to_float(
                data.get("circuit2_max_flow_temp_cooling_otc")
            ),
            circuit2_heat_eco_offset=_to_float(data.get("circuit2_heat_eco_offset")),
            circuit2_cool_eco_offset=_to_float(data.get("circuit2_cool_eco_offset")),
            # Primary compressor thermodynamics
            compressor_tg_gas_temp=_to_float(data.get("compressor_tg_gas_temp")),
            compressor_ti_liquid_temp=_to_float(data.get("compressor_ti_liquid_temp")),
            compressor_td_discharge_temp=_to_float(
                data.get("compressor_td_discharge_temp")
            ),
            compressor_te_evaporator_temp=_to_float(
                data.get("compressor_te_evaporator_temp")
            ),
            compressor_evi_valve_opening=_to_float(
                data.get("compressor_evi_indoor_expansion_valve_opening")
            ),
            compressor_evo_valve_opening=_to_float(
                data.get("compressor_evo_outdoor_expansion_valve_opening")
            ),
            # Secondary compressor (S80)
            secondary_compressor_frequency=_to_float(
                data.get("secondary_compressor_frequency")
            ),
            secondary_compressor_discharge_temp=_to_float(
                data.get("secondary_compressor_discharge_temp")
            ),
            secondary_compressor_suction_temp=_to_float(
                data.get("secondary_compressor_suction_temp")
            ),
            secondary_compressor_discharge_pressure=_to_float(
                data.get("secondary_compressor_discharge_pressure")
            ),
            secondary_compressor_suction_pressure=_to_float(
                data.get("secondary_compressor_suction_pressure")
            ),
            secondary_compressor_valve_opening=_to_float(
                data.get("secondary_compressor_valve_opening")
            ),
            # System state
            unit_power=_to_bool(data.get("unit_power")),
            pump_speed=_to_float(data.get("pump_speed")),
            operation_state_code=_to_int(data.get("operation_state_code")),
            alarm_code=_to_int(data.get("alarm_code")),
            system_status=_to_int(data.get("system_status")),
            # DHW modes
            dhw_boost=_to_bool(data.get("dhw_boost")),
            dhw_high_demand=_to_bool(data.get("dhw_high_demand")),
            # Additional temperatures
            water_outlet_2_temp=_to_float(data.get("water_outlet_2_temp")),
            water_outlet_3_temp=_to_float(data.get("water_outlet_3_temp")),
            pool_current_temp=_to_float(data.get("pool_current_temp")),
            pool_target_temp=_to_float(data.get("pool_target_temp")),
        )

        self._buffer.append(point)

    def flush(self) -> list[MetricPoint]:
        """Return all buffered points and clear the buffer."""
        points = list(self._buffer)
        self._buffer.clear()
        return points


# Modbus sentinel values indicating "no sensor" or "not configured"
_SENTINEL_VALUES = frozenset({-127, -67})


def _to_float(value: Any) -> float | None:
    """Safely convert a value to float, returning None on failure or sentinel."""
    if value is None:
        return None
    try:
        result = float(value)
        if result in _SENTINEL_VALUES:
            return None
        return result
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    """Safely convert a value to bool, returning None if not set."""
    if value is None:
        return None
    return bool(value)


def _to_int(value: Any) -> int | None:
    """Safely convert a value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
