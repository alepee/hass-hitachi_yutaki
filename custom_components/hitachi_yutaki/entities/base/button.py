"""Base button entity for Hitachi Yutaki integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from custom_components.hitachi_yutaki.const import DEVICE_TYPES, DOMAIN
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiButtonEntityDescription(ButtonEntityDescription):
    """Class describing Hitachi Yutaki button entities."""

    key: str
    translation_key: str
    icon: str | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True
    description: str | None = None
    action_fn: Callable[[Any], Any] | None = None


class HitachiYutakiButton(
    CoordinatorEntity[HitachiYutakiDataCoordinator], ButtonEntity
):
    """Representation of a Hitachi Yutaki Button."""

    entity_description: HitachiYutakiButtonEntityDescription

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiButtonEntityDescription,
        device_info: DeviceInfo,
        register_prefix: str | None = None,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = (
            f"{entry_id}_{register_prefix}_{description.key}"
            if register_prefix
            else f"{entry_id}_{description.key}"
        )
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.entity_description.action_fn:
            await self.entity_description.action_fn(self.coordinator)
            await self.coordinator.async_request_refresh()


def _create_buttons(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    descriptions: tuple[HitachiYutakiButtonEntityDescription, ...],
    device_type: DEVICE_TYPES,
    register_prefix: str | None = None,
) -> list[HitachiYutakiButton]:
    """Create button entities from descriptions."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{device_type}")},
    )

    return [
        HitachiYutakiButton(
            coordinator=coordinator,
            description=description,
            device_info=device_info,
            register_prefix=register_prefix,
        )
        for description in descriptions
    ]
