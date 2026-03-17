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
        unit_mode = _UNIT_MODE_MAP.get(unit_mode_raw) if unit_mode_raw is not None else None

        # Detect DHW active from operation_state
        operation_state = data.get("operation_state")
        dhw_active = operation_state == "operation_state_dhw_on" if operation_state else None

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
            circuit1_otc_method_heating=data.get("circuit1_otc_calculation_method_heating"),
            circuit1_otc_method_cooling=data.get("circuit1_otc_calculation_method_cooling"),
            circuit1_eco_mode=_to_bool(data.get("circuit1_eco_mode")),
            circuit2_eco_mode=_to_bool(data.get("circuit2_eco_mode")),
            circuit1_power=_to_bool(data.get("circuit1_power")),
            circuit2_power=_to_bool(data.get("circuit2_power")),
            dhw_power=_to_bool(data.get("dhw_power")),
        )

        self._buffer.append(point)

    def flush(self) -> list[MetricPoint]:
        """Return all buffered points and clear the buffer."""
        points = list(self._buffer)
        self._buffer.clear()
        return points


def _to_float(value: Any) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    """Safely convert a value to bool, returning None if not set."""
    if value is None:
        return None
    return bool(value)
