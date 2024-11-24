"""Climate platform for Hitachi Yutaki."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Final

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    PRESET_ECO,
    PRESET_NONE,
)
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_DHW,
    DOMAIN,
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    MASK_DEFROST,
    MASK_COMPRESSOR,
    PRESET_COMFORT,
    PRESET_DHW_OFF,
    PRESET_DHW_STANDARD,
    PRESET_DHW_HIGH_DEMAND,
)
from .coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiClimateEntityDescription(ClimateEntityDescription):
    """Class describing Hitachi Yutaki climate entities."""


CLIMATE_DESCRIPTIONS: Final[tuple[HitachiYutakiClimateEntityDescription, ...]] = (
    HitachiYutakiClimateEntityDescription(
        key="climate",
        translation_key="climate",
    ),
)

DHW_CLIMATE_DESCRIPTIONS: Final[tuple[HitachiYutakiClimateEntityDescription, ...]] = (
    HitachiYutakiClimateEntityDescription(
        key="dhw_climate",
        translation_key="dhw_climate",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate entities."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[HitachiYutakiClimate] = []

    # Add circuit 1 climate if configured
    if coordinator.has_heating_circuit1():
        entities.append(
            HitachiYutakiClimate(
                coordinator=coordinator,
                description=CLIMATE_DESCRIPTIONS[0],
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_1}")},
                ),
                circuit_id=1,
            )
        )

    # Add circuit 2 climate if configured
    if coordinator.has_heating_circuit2():
        entities.append(
            HitachiYutakiClimate(
                coordinator=coordinator,
                description=CLIMATE_DESCRIPTIONS[0],
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_2}")},
                ),
                circuit_id=2,
            )
        )

    # Add DHW climate if configured
    if coordinator.has_dhw():
        entities.append(
            HitachiYutakiDHWClimate(
                coordinator=coordinator,
                description=DHW_CLIMATE_DESCRIPTIONS[0],
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DHW}")},
                ),
            )
        )

    async_add_entities(entities)


class HitachiYutakiClimate(CoordinatorEntity[HitachiYutakiDataCoordinator], ClimateEntity):
    """Representation of a Hitachi Yutaki Climate."""

    entity_description: HitachiYutakiClimateEntityDescription

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiClimateEntityDescription,
        device_info: DeviceInfo,
        circuit_id: int,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._circuit_id = circuit_id
        self._register_prefix = f"circuit{circuit_id}"
        self._attr_unique_id = f"{coordinator.slave}_{self._register_prefix}_climate"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

        # Set supported features
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        # Set temperature settings
        self._attr_min_temp = 5.0
        self._attr_max_temp = 35.0
        self._attr_target_temperature_step = 0.5
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        # Set available modes
        self._attr_hvac_modes = [HVACMode.OFF]
        if coordinator.has_heating_circuit1() if circuit_id == 1 else coordinator.has_heating_circuit2():
            self._attr_hvac_modes.append(HVACMode.HEAT)
        if coordinator.has_cooling_circuit1() if circuit_id == 1 else coordinator.has_cooling_circuit2():
            self._attr_hvac_modes.append(HVACMode.COOL)
        if len(self._attr_hvac_modes) > 2:  # If both heating and cooling are available
            self._attr_hvac_modes.append(HVACMode.AUTO)

        # Set available presets
        self._attr_preset_modes = [PRESET_COMFORT, PRESET_ECO]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data is None:
            return None

        temp = self.coordinator.data.get(f"{self._register_prefix}_current_temp")
        if temp is None:
            return None

        return float(temp) / 10

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.coordinator.data is None:
            return None

        temp = self.coordinator.data.get(f"{self._register_prefix}_target_temp")
        if temp is None:
            return None

        return float(temp) / 10

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation mode."""
        if self.coordinator.data is None:
            return None

        power = self.coordinator.data.get(f"{self._register_prefix}_power")
        if power == 0:
            return HVACMode.OFF

        unit_mode = self.coordinator.data.get("unit_mode")
        if unit_mode is None:
            return None

        return {
            0: HVACMode.COOL,
            1: HVACMode.HEAT,
            2: HVACMode.AUTO,
        }.get(unit_mode)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        if self.coordinator.data is None:
            return None

        power = self.coordinator.data.get(f"{self._register_prefix}_power")
        if power == 0:
            return HVACAction.OFF

        system_status = self.coordinator.data.get("system_status", 0)

        # Check if in defrost mode
        if system_status & MASK_DEFROST:
            return HVACAction.DEFROST

        # Check if compressor is running
        if not (system_status & MASK_COMPRESSOR):
            return HVACAction.IDLE

        unit_mode = self.coordinator.data.get("unit_mode")
        if unit_mode == 0:
            return HVACAction.COOLING
        elif unit_mode == 1:
            return HVACAction.HEATING

        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self.coordinator.data is None:
            return None

        eco_mode = self.coordinator.data.get(f"{self._register_prefix}_eco_mode")
        if eco_mode is None:
            return None

        return PRESET_ECO if eco_mode == 0 else PRESET_COMFORT

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        await self.coordinator.async_write_register(
            f"{self._register_prefix}_target_temp",
            int(temperature * 10)
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_write_register(
                f"{self._register_prefix}_power",
                0
            )
            return

        # Ensure circuit is powered on
        await self.coordinator.async_write_register(
            f"{self._register_prefix}_power",
            1
        )

        # Set unit mode
        mode_map = {
            HVACMode.COOL: 0,
            HVACMode.HEAT: 1,
            HVACMode.AUTO: 2,
        }
        if hvac_mode in mode_map:
            await self.coordinator.async_write_register(
                "unit_mode",
                mode_map[hvac_mode]
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in self.preset_modes:
            return

        await self.coordinator.async_write_register(
            f"{self._register_prefix}_eco_mode",
            0 if preset_mode == PRESET_ECO else 1
        )


class HitachiYutakiDHWClimate(CoordinatorEntity[HitachiYutakiDataCoordinator], ClimateEntity):
    """Representation of a Hitachi Yutaki DHW Climate."""

    entity_description: HitachiYutakiClimateEntityDescription

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiClimateEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.slave}_dhw_climate"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

        # Set supported features
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        # Set temperature settings
        self._attr_min_temp = 30.0
        self._attr_max_temp = 60.0
        self._attr_target_temperature_step = 1.0
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        # Set available modes
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]

        # Set available presets
        self._attr_preset_modes = [
            PRESET_DHW_OFF,
            PRESET_DHW_STANDARD,
            PRESET_DHW_HIGH_DEMAND,
        ]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data is None:
            return None

        temp = self.coordinator.data.get("dhw_current_temp")
        if temp is None:
            return None

        # Convert from 2's complement if necessary (16-bit signed integer)
        if temp > 32767:  # If highest bit is set (negative number)
            temp = temp - 65536

        return float(temp) / 10

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.coordinator.data is None:
            return None

        temp = self.coordinator.data.get("dhw_target_temp")
        if temp is None:
            return None

        return float(temp) / 10

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation mode."""
        if self.coordinator.data is None:
            return None

        power = self.coordinator.data.get("dhw_power")
        return HVACMode.HEAT if power == 1 else HVACMode.OFF

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self.coordinator.data is None:
            return None

        power = self.coordinator.data.get("dhw_power")
        if power == 0:
            return PRESET_DHW_OFF

        high_demand = self.coordinator.data.get("dhw_mode")
        return PRESET_DHW_HIGH_DEMAND if high_demand == 1 else PRESET_DHW_STANDARD

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        await self.coordinator.async_write_register(
            "dhw_target_temp",
            int(temperature * 10)
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.coordinator.async_write_register(
            "dhw_power",
            1 if hvac_mode == HVACMode.HEAT else 0
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in self.preset_modes:
            return

        if preset_mode == PRESET_DHW_OFF:
            await self.coordinator.async_write_register("dhw_power", 0)
            return

        # For all other modes, ensure power is on
        await self.coordinator.async_write_register("dhw_power", 1)

        # Set high demand mode
        await self.coordinator.async_write_register(
            "dhw_mode",
            1 if preset_mode == PRESET_DHW_HIGH_DEMAND else 0
        )
