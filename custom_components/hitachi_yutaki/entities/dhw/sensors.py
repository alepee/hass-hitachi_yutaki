"""DHW sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from ...const import DEVICE_DHW
from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


DHW_DEMAND_MODE_STANDARD = "standard"
DHW_DEMAND_MODE_HIGH_DEMAND = "high_demand"


def build_dhw_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build DHW sensor entities."""
    descriptions = _build_dhw_sensor_descriptions()
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_DHW)


def _dhw_demand_mode_value(
    coordinator: HitachiYutakiDataCoordinator,
) -> str | None:
    """Return the DHW demand mode as a translated enum value."""
    value = coordinator.data.get("dhw_demand_mode")
    if value is None:
        return None
    return DHW_DEMAND_MODE_HIGH_DEMAND if value else DHW_DEMAND_MODE_STANDARD


def _build_dhw_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build DHW sensor descriptions."""
    return (
        HitachiYutakiSensorEntityDescription(
            key="dhw_demand_mode",
            translation_key="dhw_demand_mode",
            description="DHW demand mode status (standard or high demand)",
            device_class=SensorDeviceClass.ENUM,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            icon="mdi:water-thermometer",
            options=[DHW_DEMAND_MODE_STANDARD, DHW_DEMAND_MODE_HIGH_DEMAND],
            condition=lambda c: (
                c.has_dhw()
                and "dhw_demand_mode" in c.api_client.register_map.all_registers
            ),
            value_fn=_dhw_demand_mode_value,
        ),
    )
