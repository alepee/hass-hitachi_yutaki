"""Switch platform for Hitachi Yutaki."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_CONTROL_UNIT,
    DEVICE_DHW,
    DEVICE_POOL,
    DOMAIN,
)
from .coordinator import HitachiYutakiDataCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class HitachiYutakiSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Hitachi Yutaki switch entities."""

    key: str
    translation_key: str
    icon: str | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True

    description: str | None = None
    get_fn: Callable[[Any, int | None], bool | None] | None = None
    set_fn: Callable[[Any, int | None, bool], Any] | None = None


UNIT_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="power",
        translation_key="power",
        icon="mdi:power",
        description="Main power switch for the heat pump unit",
        get_fn=lambda api, _: api.get_unit_power(),
        set_fn=lambda api, _, value: api.set_unit_power(value),
    ),
)

CIRCUIT_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="thermostat",
        translation_key="thermostat",
        description="Enable/disable the Modbus thermostat function for this circuit",
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda api, circuit_id: api.get_circuit_thermostat(circuit_id),
        set_fn=lambda api, circuit_id, value: api.set_circuit_thermostat(
            circuit_id, value
        ),
    ),
    HitachiYutakiSwitchEntityDescription(
        key="eco_mode",
        translation_key="eco_mode",
        icon="mdi:leaf",
        description="Enable/disable ECO mode which applies a temperature offset to save energy",
        get_fn=lambda api, circuit_id: api.get_circuit_eco_mode(circuit_id),
        set_fn=lambda api, circuit_id, value: api.set_circuit_eco_mode(
            circuit_id, value
        ),
    ),
)

DHW_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="boost",
        translation_key="boost",
        description="Temporarily boost DHW production",
        get_fn=lambda api, _: api.get_dhw_boost(),
        set_fn=lambda api, _, value: api.set_dhw_boost(value),
    ),
)

POOL_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="power",
        translation_key="power",
        description="Power switch for swimming pool heating",
        get_fn=lambda api, _: api.get_pool_power(),
        set_fn=lambda api, _, value: api.set_pool_power(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switches."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[HitachiYutakiSwitch] = []

    # Add unit switches
    entities.extend(
        HitachiYutakiSwitch(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
            ),
        )
        for description in UNIT_SWITCHES
    )

    # Add circuit 1 switches if configured
    if coordinator.has_heating_circuit1():
        for description in CIRCUIT_SWITCHES:
            # Skip thermostat switches if thermostat is not available
            if description.key == "thermostat" and not coordinator.data.get(
                "circuit1_thermostat_available", False
            ):
                continue
            entities.append(
                HitachiYutakiSwitch(
                    coordinator=coordinator,
                    description=description,
                    device_info=DeviceInfo(
                        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_1}")},
                    ),
                    register_prefix="circuit1",
                )
            )

    # Add circuit 2 switches if configured
    if coordinator.has_heating_circuit2():
        for description in CIRCUIT_SWITCHES:
            # Skip thermostat switches if thermostat is not available
            if description.key == "thermostat" and not coordinator.data.get(
                "circuit2_thermostat_available", False
            ):
                continue
            entities.append(
                HitachiYutakiSwitch(
                    coordinator=coordinator,
                    description=description,
                    device_info=DeviceInfo(
                        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_2}")},
                    ),
                    register_prefix="circuit2",
                )
            )

    # Add DHW switches if configured
    if coordinator.has_dhw():
        entities.extend(
            HitachiYutakiSwitch(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DHW}")},
                ),
                register_prefix="dhw",
            )
            for description in DHW_SWITCHES
        )

    # Add pool switches if configured
    if coordinator.has_pool():
        entities.extend(
            HitachiYutakiSwitch(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_POOL}")},
                ),
                register_prefix="pool",
            )
            for description in POOL_SWITCHES
        )

    async_add_entities(entities)


class HitachiYutakiSwitch(
    CoordinatorEntity[HitachiYutakiDataCoordinator], SwitchEntity
):
    """Representation of a Hitachi Yutaki Switch."""

    entity_description: HitachiYutakiSwitchEntityDescription

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiSwitchEntityDescription,
        device_info: DeviceInfo,
        register_prefix: str | None = None,
    ) -> None:
        """Initialize the switch."""
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
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if self.coordinator.data is None or not self.entity_description.get_fn:
            return None

        return self.entity_description.get_fn(
            self.coordinator.api_client, self._circuit_id
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if self.entity_description.set_fn:
            await self.entity_description.set_fn(
                self.coordinator.api_client, self._circuit_id, True
            )
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if self.entity_description.set_fn:
            await self.entity_description.set_fn(
                self.coordinator.api_client, self._circuit_id, False
            )
            await self.coordinator.async_request_refresh()
