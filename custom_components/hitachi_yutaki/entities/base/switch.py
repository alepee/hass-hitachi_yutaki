"""Base switch entity for Hitachi Yutaki integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...const import DEVICE_TYPES, DOMAIN
from ...coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiSwitchEntityDescription:
    """Describes a Hitachi Yutaki switch entity."""

    key: str
    name: str
    get_fn: Callable[[Any, int | None], bool | None]
    set_fn: Callable[[Any, int | None, bool], bool]
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

        # Set name
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        circuit_id = self._get_circuit_id()
        await self._description.set_fn(self._coordinator.api_client, circuit_id, True)

        # Update coordinator data
        if self._register_prefix:
            register_key = f"{self._register_prefix}_{self._description.key}"
        else:
            register_key = self._description.key
        self._coordinator.data[register_key] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if not self._description.set_fn:
            return

        # Use dedicated API method
        circuit_id = self._get_circuit_id()
        await self._description.set_fn(self._coordinator.api_client, circuit_id, False)

        # Update coordinator data
        if self._register_prefix:
            register_key = f"{self._register_prefix}_{self._description.key}"
        else:
            register_key = self._description.key
        self._coordinator.data[register_key] = False
        self.async_write_ha_state()


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
