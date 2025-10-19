"""DHW binary sensor descriptions."""

from __future__ import annotations

from typing import Final

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from .base import HitachiYutakiBinarySensorEntityDescription

DHW_BINARY_SENSORS: Final[tuple[HitachiYutakiBinarySensorEntityDescription, ...]] = (
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
