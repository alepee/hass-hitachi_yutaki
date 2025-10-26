"""DHW sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...const import DEVICE_DHW
from ..base.sensor import HitachiYutakiSensor, HitachiYutakiSensorEntityDescription

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_dhw_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build DHW sensor entities."""
    from ..base.sensor import _create_sensors

    descriptions = _build_dhw_sensor_descriptions()
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_DHW)


def _build_dhw_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build DHW sensor descriptions."""
    # DHW sensors tuple is empty in the source
    return ()
