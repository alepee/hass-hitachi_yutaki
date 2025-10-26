"""Base number entity and description for Hitachi Yutaki."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...const import DEVICE_TYPES, DOMAIN
from ...coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiNumberEntityDescription(NumberEntityDescription):
    """Class describing Hitachi Yutaki number entities."""

    key: str
    translation_key: str
    max_value: None = None
    min_value: None = None
    mode: NumberMode | None = None
    native_max_value: float | None = None
    native_min_value: float | None = None
    native_step: float | None = None
    native_unit_of_measurement: str | None = None
    step: None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True

    description: str | None = None
    get_fn: Callable[[Any, int | None], float | None] | None = None
    set_fn: Callable[[Any, int | None, float], Any] | None = None
    condition: Callable[[HitachiYutakiDataCoordinator], bool] | None = None


def _create_numbers(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    descriptions: tuple[HitachiYutakiNumberEntityDescription, ...],
    device_type: DEVICE_TYPES,
    register_prefix: str,
    skip_cooling: bool = False,
) -> list[HitachiYutakiNumber]:
    """Create number entities for a specific device type.

    Args:
        coordinator: The data coordinator
        entry_id: The config entry ID
        descriptions: Number descriptions to create
        device_type: Device type identifier (e.g., DEVICE_CIRCUIT_1)
        register_prefix: Register prefix for the entity
        skip_cooling: Whether to skip cooling-related entities

    Returns:
        List of created number entities

    """
    entities = []
    for description in descriptions:
        # Skip cooling related entities if cooling is not available
        if skip_cooling and "cool" in description.key:
            continue
        # Skip entities that don't meet their condition
        if description.condition is not None and not description.condition(coordinator):
            continue
        entities.append(
            HitachiYutakiNumber(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry_id}_{device_type}")},
                ),
                register_prefix=register_prefix,
            )
        )
    return entities


class HitachiYutakiNumber(
    CoordinatorEntity[HitachiYutakiDataCoordinator], NumberEntity
):
    """Representation of a Hitachi Yutaki Number."""

    entity_description: HitachiYutakiNumberEntityDescription

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiNumberEntityDescription,
        device_info: DeviceInfo,
        register_prefix: str | None = None,
    ) -> None:
        """Initialize the number entity."""
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
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        if self.coordinator.data is None or not self.entity_description.get_fn:
            return None

        return self.entity_description.get_fn(
            self.coordinator.api_client, self._circuit_id
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.set_fn:
            await self.entity_description.set_fn(
                self.coordinator.api_client, self._circuit_id, value
            )
            await self.coordinator.async_request_refresh()

    def set_native_value(self, value: float) -> None:
        """Set new value."""
        raise NotImplementedError
