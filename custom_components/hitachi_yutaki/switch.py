"""Switch platform for Hitachi Heat Pump."""

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
from .coordinator import HitachiHeatPumpDataCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class HitachiHeatPumpSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Hitachi Heat Pump switch entities."""

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


UNIT_SWITCHES: Final[tuple[HitachiHeatPumpSwitchEntityDescription, ...]] = (
    HitachiHeatPumpSwitchEntityDescription(
        key="power",
        translation_key="power",
        icon="mdi:power",
        description="Main power switch for the heat pump unit",
        register_key="unit_power",
    ),
)

CIRCUIT_SWITCHES: Final[tuple[HitachiHeatPumpSwitchEntityDescription, ...]] = (
    HitachiHeatPumpSwitchEntityDescription(
        key="thermostat",
        translation_key="thermostat",
        description="Enable/disable the Modbus thermostat function for this circuit",
        register_key="thermostat",
        entity_category=EntityCategory.CONFIG,
    ),
    HitachiHeatPumpSwitchEntityDescription(
        key="eco_mode",
        translation_key="eco_mode",
        icon="mdi:leaf",
        description="Enable/disable ECO mode which applies a temperature offset to save energy",
        register_key="eco_mode",
        state_on=0,
        state_off=1,
    ),
)

DHW_SWITCHES: Final[tuple[HitachiHeatPumpSwitchEntityDescription, ...]] = (
    HitachiHeatPumpSwitchEntityDescription(
        key="boost",
        translation_key="boost",
        description="Temporarily boost DHW production",
        register_key="boost",
    ),
)

POOL_SWITCHES: Final[tuple[HitachiHeatPumpSwitchEntityDescription, ...]] = (
    HitachiHeatPumpSwitchEntityDescription(
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
    coordinator: HitachiHeatPumpDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[HitachiHeatPumpSwitch] = []

    # Add unit switches
    entities.extend(
        HitachiHeatPumpSwitch(
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
                HitachiHeatPumpSwitch(
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
                HitachiHeatPumpSwitch(
                    coordinator=coordinator,
                    description=description,
                    device_info=DeviceInfo(
                        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_2}")},
                    ),
                    register_prefix="circuit2",
                )
            )

    # Add DHW switches if configured and supported by profile (if any)
    if coordinator.has_dhw() and (
        coordinator.profile is None
        or getattr(coordinator.profile, "supports_dhw", True)
    ):
        entities.extend(
            HitachiHeatPumpSwitch(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DHW}")},
                ),
                register_prefix="dhw",
            )
            for description in DHW_SWITCHES
        )

    # Add pool switches if configured and supported by profile (if any)
    if coordinator.has_pool() and (
        coordinator.profile is None
        or getattr(coordinator.profile, "supports_pool", True)
    ):
        entities.extend(
            HitachiHeatPumpSwitch(
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


class HitachiHeatPumpSwitch(
    CoordinatorEntity[HitachiHeatPumpDataCoordinator], SwitchEntity
):
    """Representation of a Hitachi Heat Pump Switch."""

    entity_description: HitachiHeatPumpSwitchEntityDescription

    def __init__(
        self,
        coordinator: HitachiHeatPumpDataCoordinator,
        description: HitachiHeatPumpSwitchEntityDescription,
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
            f"{entry_id}_{coordinator.device_id}_{register_prefix}_{description.key}"
            if register_prefix
            else f"{entry_id}_{coordinator.device_id}_{description.key}"
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
        if self.coordinator.data is None or self._register_key is None:
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
                self._register_key, register_value
            )
        except (ValueError, TypeError):
            _LOGGER.error(
                "Failed to turn on %s: invalid value %s",
                self.entity_id,
                self.entity_description.state_on,
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
                register_value,
            )
            await self.coordinator.async_write_register(
                self._register_key, register_value
            )
        except (ValueError, TypeError) as e:
            _LOGGER.error(
                "Failed to turn off %s: invalid value %s - Error: %s",
                self.entity_id,
                self.entity_description.state_off,
                str(e),
            )
