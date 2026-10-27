"""Gateway sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from ...const import DEVICE_GATEWAY
from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


# "Central Mode" register values (ATW-MBS-02 1088 / 1073, HC-A(16/64)MB offset 139).
CENTRAL_CONTROL_MODES = {0: "local", 1: "air", 2: "water", 3: "full"}


def build_gateway_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build gateway sensor entities."""
    descriptions = _build_gateway_sensor_descriptions()
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_GATEWAY)


def _central_control_mode_value(
    coordinator: HitachiYutakiDataCoordinator,
) -> str | None:
    """Return the gateway's central control mode as an enum value."""
    return CENTRAL_CONTROL_MODES.get(coordinator.data.get("central_control_mode"))


def _build_gateway_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build gateway sensor descriptions."""
    return (
        HitachiYutakiSensorEntityDescription(
            key="system_state",
            translation_key="system_state",
            description="System state",
            device_class=SensorDeviceClass.ENUM,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:state-machine",
            value_fn=lambda coordinator: coordinator.data.get("system_state"),
        ),
        HitachiYutakiSensorEntityDescription(
            key="central_control_mode",
            translation_key="central_control_mode",
            description=(
                "Which functions the gateway controls centrally (local: the LCD "
                "ignores Modbus writes; air; water; full)"
            ),
            device_class=SensorDeviceClass.ENUM,
            options=list(CENTRAL_CONTROL_MODES.values()),
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:remote",
            condition=lambda c: c.api_client.supports_key("central_control_mode"),
            value_fn=_central_control_mode_value,
        ),
    )
