"""Circuit sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.hitachi_yutaki.const import CIRCUIT_IDS, DEVICE_TYPES

from ..base.sensor import HitachiYutakiSensor, HitachiYutakiSensorEntityDescription

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_circuit_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    circuit_id: CIRCUIT_IDS,
    device_type: DEVICE_TYPES,
) -> list[HitachiYutakiSensor]:
    """Build circuit sensor entities."""
    from ..base.sensor import _create_sensors

    descriptions = _build_circuit_sensor_descriptions(circuit_id)
    return _create_sensors(coordinator, entry_id, descriptions, device_type)


def _build_circuit_sensor_descriptions(
    circuit_id: CIRCUIT_IDS,
) -> tuple[HitachiYutakiSensorEntityDescription, ...]:
    """Build circuit sensor descriptions."""
    # Circuit sensors are currently handled in the base sensor platform
    # This can be expanded if circuit-specific sensors are added in the future
    return ()
