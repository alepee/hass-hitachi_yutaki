"""Switch platform for Hitachi Yutaki."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Final, Any

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DEVICE_CONTROL_UNIT,
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_DHW,
    DEVICE_POOL,
)
from .coordinator import HitachiYutakiDataCoordinator

import logging

_LOGGER = logging.getLogger(__name__)


@dataclass
class HitachiYutakiSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Hitachi Yutaki switch entities."""

    register_key: str | None = None
    state_on: int = 1
    state_off: int = 0


UNIT_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="power",
        name="Power",
        register_key="unit_power",
    ),
)

CIRCUIT_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="power",
        name="Power",
        register_key="power",
    ),
    # @TODO: Check if thermostat should be widely available
    HitachiYutakiSwitchEntityDescription(
        key="thermostat",
        name="Thermostat",
        register_key="thermostat",
        entity_category=EntityCategory.CONFIG,
    ),
    HitachiYutakiSwitchEntityDescription(
        key="eco_mode",
        name="ECO Mode",
        register_key="eco_mode",
        state_on=0,
        state_off=1,
        icon="mdi:leaf",
    ),
)

DHW_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="power",
        name="Power",
        register_key="power",
    ),
    HitachiYutakiSwitchEntityDescription(
        key="boost",
        name="Boost",
        register_key="boost",
    ),
    HitachiYutakiSwitchEntityDescription(
        key="antilegionella",
        name="Anti-legionella",
        register_key="antilegionella_power",
        entity_category=EntityCategory.CONFIG,
    ),
)

POOL_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="power",
        name="Power",
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
        self._attr_unique_id = f"{coordinator.slave}_{register_prefix}_{description.key}" if register_prefix else f"{coordinator.slave}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if (
            self.coordinator.data is None
            or self._register_key is None
        ):
            return None

        try:
            value = self.coordinator.data.get(self._register_key)
            if value is None:
                return None

            return int(value) == self.entity_description.state_on
        except (ValueError, TypeError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if self._register_key is None:
            return

        try:
            register_value = int(self.entity_description.state_on)
            await self.coordinator.async_write_register(
                self._register_key,
                register_value
            )
        except (ValueError, TypeError):
            _LOGGER.error(
                "Failed to turn on %s: invalid value %s",
                self.entity_id,
                self.entity_description.state_on
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if self._register_key is None:
            return

        try:
            register_value = int(self.entity_description.state_off)
            _LOGGER.debug(
                "Turning off %s: register_key=%s, value=%s",
                self.entity_id,
                self._register_key,
                register_value
            )
            await self.coordinator.async_write_register(
                self._register_key,
                register_value
            )
        except (ValueError, TypeError) as e:
            _LOGGER.error(
                "Failed to turn off %s: invalid value %s - Error: %s",
                self.entity_id,
                self.entity_description.state_off,
                str(e)
            )
        except Exception as e:
            _LOGGER.error(
                "Unexpected error turning off %s: %s - %s",
                self.entity_id,
                type(e).__name__,
                str(e)
            )
