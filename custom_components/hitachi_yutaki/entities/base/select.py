"""Base select entity for Hitachi Yutaki integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from custom_components.hitachi_yutaki.const import DEVICE_TYPES, DOMAIN
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiSelectEntityDescription(SelectEntityDescription):
    """Class describing Hitachi Yutaki select entities."""

    key: str
    translation_key: str
    options: list[str] | None = None
    value_map: dict[str, Any] | None = None
    condition: Callable[[Any], bool] | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = False
    description: str | None = None
    get_fn: Callable[[Any, int | None], str | None] | None = None
    set_fn: Callable[[Any, int | None, Any], Any] | None = None


class HitachiYutakiSelect(
    CoordinatorEntity[HitachiYutakiDataCoordinator], SelectEntity
):
    """Representation of a Hitachi Yutaki Select."""

    entity_description: HitachiYutakiSelectEntityDescription

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiSelectEntityDescription,
        device_info: DeviceInfo,
        register_prefix: str | None = None,
    ) -> None:
        """Initialize the select."""
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

        # Extract circuit_id if applicable
        self._circuit_id = (
            int(register_prefix.replace("circuit", ""))
            if register_prefix and register_prefix.startswith("circuit")
            else None
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if (
            not self.coordinator.data
            or not self.entity_description.value_map
            or not self.entity_description.get_fn
        ):
            return None

        value = self.entity_description.get_fn(
            self.coordinator.api_client, self._circuit_id
        )

        if value is None:
            return None

        return next(
            (k for k, v in self.entity_description.value_map.items() if v == value),
            None,
        )

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        raise NotImplementedError("Async version should be used instead")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if (
            not self.entity_description.value_map
            or option not in self.entity_description.value_map
            or not self.entity_description.set_fn
        ):
            return

        value = self.entity_description.value_map[option]
        await self.entity_description.set_fn(
            self.coordinator.api_client, self._circuit_id, value
        )
        await self.coordinator.async_request_refresh()


def _create_selects(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    descriptions: tuple[HitachiYutakiSelectEntityDescription, ...],
    device_type: DEVICE_TYPES,
    register_prefix: str | None = None,
) -> list[HitachiYutakiSelect]:
    """Create select entities from descriptions."""
    entities = []
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{device_type}")},
    )

    for description in descriptions:
        if description.condition and not description.condition(coordinator):
            continue

        entities.append(
            HitachiYutakiSelect(
                coordinator=coordinator,
                description=description,
                device_info=device_info,
                register_prefix=register_prefix,
            )
        )

    return entities
