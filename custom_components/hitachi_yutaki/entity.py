"""Base entity for Hitachi Yutaki integration."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HitachiYutakiDataCoordinator


class HitachiYutakiEntity(CoordinatorEntity[HitachiYutakiDataCoordinator]):
    """Base class for all Hitachi Yutaki entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        entry_id: str,
        key: str,
        device_type: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{device_type}")},
        )
