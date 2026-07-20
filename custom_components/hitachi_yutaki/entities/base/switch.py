"""Base switch entity for Hitachi Yutaki integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...const import DEVICE_TYPES, DOMAIN
from ...coordinator import HitachiYutakiDataCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class HitachiYutakiSwitchEntityDescription:
    """Describes a Hitachi Yutaki switch entity."""

    key: str
    get_fn: Callable[[Any, int | None], bool | None]
    set_fn: Callable[[Any, int | None, bool], bool]
    # Either a hardcoded English name (legacy switches) or a translation_key
    # that opts the entity into Home Assistant's localized naming.
    name: str | None = None
    translation_key: str | None = None
    icon: str | None = None
    entity_category: str | None = None
    condition: Callable[[HitachiYutakiDataCoordinator], bool] | None = None


class HitachiYutakiSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Hitachi Yutaki switch."""

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiSwitchEntityDescription,
        device_info: DeviceInfo,
        register_prefix: str | None = None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._description = description
        self._device_info = device_info
        self._register_prefix = register_prefix

        # Set unique_id
        entry_id = coordinator.config_entry.entry_id
        if register_prefix:
            self._attr_unique_id = f"{entry_id}_{register_prefix}_{description.key}"
        else:
            self._attr_unique_id = f"{entry_id}_{description.key}"

        # Set name: a translation_key opts the entity into HA's localized
        # naming (requires has_entity_name); otherwise fall back to the
        # hardcoded English name used by the legacy switches.
        if description.translation_key:
            self._attr_has_entity_name = True
            self._attr_translation_key = description.translation_key
        else:
            self._attr_name = description.name

        # Set icon
        if description.icon:
            self._attr_icon = description.icon

        # Set entity category
        if description.entity_category:
            self._attr_entity_category = description.entity_category

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return self._device_info

    def _get_circuit_id(self) -> int | None:
        """Extract circuit ID from register prefix."""
        if self._register_prefix and self._register_prefix.startswith("circuit"):
            try:
                return int(self._register_prefix.replace("circuit", ""))
            except ValueError:
                pass
        return None

    @property
    def is_on(self) -> bool | None:
        """Return if the switch is on."""
        circuit_id = self._get_circuit_id()
        return self._description.get_fn(self._coordinator.api_client, circuit_id)

    @property
    def _register_key(self) -> str:
        """Return the coordinator data key for this switch."""
        if self._register_prefix:
            return f"{self._register_prefix}_{self._description.key}"
        return self._description.key

    async def _async_set(self, value: bool) -> None:
        """Write a value via set_fn and re-sync from the live device state.

        ``set_fn`` returns a bool success flag. On failure we do not apply an
        optimistic state, we log and request a refresh so the entity reverts to
        the real device state. On success we also request a refresh because
        ``is_on`` reads from the live ``api_client`` (not ``coordinator.data``).
        """
        circuit_id = self._get_circuit_id()
        success = await self._description.set_fn(
            self._coordinator.api_client, circuit_id, value
        )

        if not success:
            _LOGGER.warning(
                "Failed to set %s to %s for %s",
                self._register_key,
                value,
                self._attr_unique_id,
            )
            await self._coordinator.async_request_refresh()
            return

        # Re-sync from the live state. is_on reads from api_client, so the
        # refresh (not an optimistic coordinator.data write) drives the UI.
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if not self._description.set_fn:
            return
        await self._async_set(False)


def _create_switches(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    descriptions: tuple[HitachiYutakiSwitchEntityDescription, ...],
    device_type: DEVICE_TYPES,
    register_prefix: str | None = None,
) -> list[HitachiYutakiSwitch]:
    """Create switch entities for a specific device type."""
    entities = []
    for description in descriptions:
        # Skip entities that don't meet their condition
        if description.condition is not None and not description.condition(coordinator):
            continue
        entities.append(
            HitachiYutakiSwitch(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry_id}_{device_type}")},
                ),
                register_prefix=register_prefix,
            )
        )
    return entities
