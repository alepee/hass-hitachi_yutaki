"""Switch platform for Hitachi Yutaki."""

from __future__ import annotations

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

    register_key: str | None = None
    state_on: int = 1
    state_off: int = 0
    description: str | None = None


UNIT_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="power",
        translation_key="power",
        icon="mdi:power",
        description="Main power switch for the heat pump unit",
        register_key="unit_power",
    ),
)

CIRCUIT_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="thermostat",
        translation_key="thermostat",
        description="Enable/disable the Modbus thermostat function for this circuit",
        register_key="thermostat",
        entity_category=EntityCategory.CONFIG,
    ),
    HitachiYutakiSwitchEntityDescription(
        key="eco_mode",
        translation_key="eco_mode",
        icon="mdi:leaf",
        description="Enable/disable ECO mode which applies a temperature offset to save energy",
        register_key="eco_mode",
        state_on=0,
        state_off=1,
    ),
)

DHW_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="boost",
        translation_key="boost",
        description="Temporarily boost DHW production",
        register_key="boost",
    ),
)

POOL_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="power",
        translation_key="power",
        description="Power switch for swimming pool heating",
        register_key="power",
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
        self.register_prefix = register_prefix
        self._register_key = (
            f"{register_prefix}_{description.register_key}"
            if register_prefix
            else description.register_key
        )
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

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if self.coordinator.data is None:
            return None

        try:
            # Map entity key to corresponding API getter
            if self.entity_description.key == "power" and not self.register_prefix:
                value = self.coordinator.api_client.get_unit_power()
            elif self.entity_description.key == "thermostat" and self.register_prefix:
                circuit_id = int(self.register_prefix.replace("circuit", ""))
                value = self.coordinator.api_client.get_circuit_thermostat(circuit_id)
            elif self.entity_description.key == "eco_mode" and self.register_prefix:
                circuit_id = int(self.register_prefix.replace("circuit", ""))
                is_eco = self.coordinator.api_client.get_circuit_eco_mode(circuit_id)
                # For eco_mode switch, state_on=0 means ON, so we return is_eco directly
                return is_eco
            elif (
                self.entity_description.key == "boost" and self.register_prefix == "dhw"
            ):
                value = self.coordinator.api_client.get_dhw_boost()
            elif (
                self.entity_description.key == "power"
                and self.register_prefix == "pool"
            ):
                value = self.coordinator.api_client.get_pool_power()
            else:
                return None

            return value
        except (ValueError, TypeError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            # Map entity key to corresponding API setter
            if self.entity_description.key == "power" and not self.register_prefix:
                await self.coordinator.api_client.set_unit_power(True)
            elif self.entity_description.key == "thermostat" and self.register_prefix:
                circuit_id = int(self.register_prefix.replace("circuit", ""))
                await self.coordinator.api_client.set_circuit_thermostat(
                    circuit_id, True
                )
            elif self.entity_description.key == "eco_mode" and self.register_prefix:
                circuit_id = int(self.register_prefix.replace("circuit", ""))
                await self.coordinator.api_client.set_circuit_eco_mode(circuit_id, True)
            elif (
                self.entity_description.key == "boost" and self.register_prefix == "dhw"
            ):
                await self.coordinator.api_client.set_dhw_boost(True)
            elif (
                self.entity_description.key == "power"
                and self.register_prefix == "pool"
            ):
                await self.coordinator.api_client.set_pool_power(True)
            else:
                _LOGGER.error("Unknown switch entity: %s", self.entity_description.key)
                return

            await self.coordinator.async_request_refresh()
        except (ValueError, TypeError) as e:
            _LOGGER.error(
                "Failed to turn on %s: %s",
                self.entity_id,
                str(e),
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        try:
            # Map entity key to corresponding API setter
            if self.entity_description.key == "power" and not self.register_prefix:
                await self.coordinator.api_client.set_unit_power(False)
            elif self.entity_description.key == "thermostat" and self.register_prefix:
                circuit_id = int(self.register_prefix.replace("circuit", ""))
                await self.coordinator.api_client.set_circuit_thermostat(
                    circuit_id, False
                )
            elif self.entity_description.key == "eco_mode" and self.register_prefix:
                circuit_id = int(self.register_prefix.replace("circuit", ""))
                await self.coordinator.api_client.set_circuit_eco_mode(
                    circuit_id, False
                )
            elif (
                self.entity_description.key == "boost" and self.register_prefix == "dhw"
            ):
                await self.coordinator.api_client.set_dhw_boost(False)
            elif (
                self.entity_description.key == "power"
                and self.register_prefix == "pool"
            ):
                await self.coordinator.api_client.set_pool_power(False)
            else:
                _LOGGER.error("Unknown switch entity: %s", self.entity_description.key)
                return

            await self.coordinator.async_request_refresh()
        except (ValueError, TypeError) as e:
            _LOGGER.error(
                "Failed to turn off %s: %s",
                self.entity_id,
                str(e),
            )
