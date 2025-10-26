"""DHW binary sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from ...const import DEVICE_DHW
from ..base.binary_sensor import (
    HitachiYutakiBinarySensor,
    HitachiYutakiBinarySensorEntityDescription,
    _create_binary_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_dhw_binary_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiBinarySensor]:
    """Build DHW binary sensor entities."""
    descriptions = _build_dhw_binary_sensor_descriptions()
    return _create_binary_sensors(coordinator, entry_id, descriptions, DEVICE_DHW)


def _build_dhw_binary_sensor_descriptions() -> tuple[
    HitachiYutakiBinarySensorEntityDescription, ...
]:
    """Build DHW binary sensor descriptions."""
    return (
        HitachiYutakiBinarySensorEntityDescription(
            key="antilegionella_cycle",
            translation_key="antilegionella_cycle",
            icon="mdi:biohazard",
            description="Indicates if an anti-legionella cycle is currently running",
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda coordinator: coordinator.api_client.is_antilegionella_active,
            condition=lambda c: c.has_dhw(),
        ),
    )
