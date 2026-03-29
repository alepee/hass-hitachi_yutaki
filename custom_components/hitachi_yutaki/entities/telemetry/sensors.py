"""Telemetry diagnostic sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.typing import StateType

from ...const import DEVICE_GATEWAY, DOMAIN
from ..base.sensor import HitachiYutakiSensor, HitachiYutakiSensorEntityDescription

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


class HitachiYutakiTelemetrySensor(HitachiYutakiSensor):
    """Telemetry diagnostic sensor with telemetry-specific attributes."""

    @property
    def native_value(self) -> StateType:
        """Return the telemetry level."""
        collector = self.coordinator.telemetry_collector
        if collector is not None:
            return collector.level.value
        return "off"

    @property
    def options(self) -> list[str]:
        """Return valid states for the ENUM sensor."""
        return ["off", "on"]

    @property
    def available(self) -> bool:
        """Telemetry status is always available."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return telemetry diagnostic attributes."""
        c = self.coordinator
        attrs: dict[str, Any] = {}

        if c.telemetry_collector is not None:
            attrs["points_buffered"] = c.telemetry_collector.buffer_size

        if c.telemetry_last_send is not None:
            attrs["last_send"] = c.telemetry_last_send.isoformat()

        attrs["send_failures"] = c.telemetry_send_failures

        return attrs


def build_telemetry_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build telemetry diagnostic sensor entities."""
    device_info = DeviceInfo(identifiers={(DOMAIN, f"{entry_id}_{DEVICE_GATEWAY}")})

    description = HitachiYutakiSensorEntityDescription(
        key="telemetry_status",
        translation_key="telemetry_status",
        description="Current telemetry opt-in level",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chart-line",
    )

    return [HitachiYutakiTelemetrySensor(coordinator, description, device_info)]
