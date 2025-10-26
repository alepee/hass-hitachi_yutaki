"""Control unit binary sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from ...const import DEVICE_CONTROL_UNIT
from ..base.binary_sensor import (
    HitachiYutakiBinarySensor,
    HitachiYutakiBinarySensorEntityDescription,
    _create_binary_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_control_unit_binary_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiBinarySensor]:
    """Build control unit binary sensor entities."""
    descriptions = _build_control_unit_binary_sensor_descriptions()
    return _create_binary_sensors(
        coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT
    )


def _build_control_unit_binary_sensor_descriptions() -> tuple[
    HitachiYutakiBinarySensorEntityDescription, ...
]:
    """Build control unit binary sensor descriptions."""
    return (
        HitachiYutakiBinarySensorEntityDescription(
            key="defrost",
            translation_key="defrost",
            icon="mdi:snowflake",
            description="Indicates if the unit is currently in defrost mode",
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda coordinator: coordinator.api_client.is_defrosting,
        ),
        HitachiYutakiBinarySensorEntityDescription(
            key="solar",
            translation_key="solar",
            icon="mdi:solar-power",
            description="Indicates if the solar system is active",
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda coordinator: coordinator.api_client.is_solar_active,
            entity_registry_enabled_default=False,
        ),
        HitachiYutakiBinarySensorEntityDescription(
            key="compressor",
            translation_key="compressor",
            icon="mdi:heat-pump",
            description="Indicates if the compressor is running",
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda coordinator: coordinator.api_client.is_compressor_running,
        ),
        HitachiYutakiBinarySensorEntityDescription(
            key="boiler",
            translation_key="boiler",
            icon="mdi:resistor",
            description="Indicates if the backup boiler is active",
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda coordinator: coordinator.api_client.is_boiler_active,
            condition=lambda c: c.profile.supports_boiler,
        ),
        HitachiYutakiBinarySensorEntityDescription(
            key="dhw_heater",
            translation_key="dhw_heater",
            icon="mdi:water-boiler",
            description="Indicates if the DHW electric heater is active",
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda coordinator: coordinator.api_client.is_dhw_heater_active,
            condition=lambda c: c.has_dhw(),
        ),
        HitachiYutakiBinarySensorEntityDescription(
            key="space_heater",
            translation_key="space_heater",
            description="Indicates if the space heating electric heater is active",
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda coordinator: coordinator.api_client.is_space_heater_active,
            entity_registry_enabled_default=False,
        ),
        HitachiYutakiBinarySensorEntityDescription(
            key="smart_function",
            translation_key="smart_function",
            icon="mdi:home-automation",
            description="Indicates if the smart grid function is active",
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda coordinator: coordinator.api_client.is_smart_function_active,
            entity_registry_enabled_default=False,
        ),
    )
