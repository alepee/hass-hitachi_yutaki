"""Button platform for Hitachi Yutaki."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_DHW,
    DOMAIN,
)
from .coordinator import HitachiYutakiDataCoordinator


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


DHW_BUTTONS: Final[tuple[HitachiYutakiButtonEntityDescription, ...]] = (
    HitachiYutakiButtonEntityDescription(
        key="antilegionella",
        translation_key="antilegionella",
        icon="mdi:biohazard",
        description="Start a high temperature anti-legionella treatment cycle. Once started, the cycle cannot be stopped.",
        entity_registry_enabled_default=True,
        action_fn=lambda coordinator: coordinator.api_client.start_dhw_antilegionella(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button entities."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[HitachiYutakiButton] = []

    # Add DHW buttons if configured
    if coordinator.has_dhw():
        entities.extend(
            HitachiYutakiButton(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DHW}")},
                ),
                register_prefix="dhw",
            )
            for description in DHW_BUTTONS
        )

    async_add_entities(entities)


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
