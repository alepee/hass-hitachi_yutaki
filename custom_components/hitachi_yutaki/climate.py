"""Climate platform for Hitachi Yutaki integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HitachiYutakiDataUpdateCoordinator, HitachiYutakiEntity
from .const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_DEFROST,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    DOMAIN,
    MASK_CIRCUIT1_COOLING,
    MASK_CIRCUIT1_HEATING,
    MASK_CIRCUIT2_COOLING,
    MASK_CIRCUIT2_HEATING,
    MASK_DEFROST,
    OPERATION_MODE_AUTO,
    OPERATION_MODE_COOL,
    OPERATION_MODE_HEAT,
    PRESET_COMFORT,
    PRESET_ECO,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hitachi Yutaki climate platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    system_config = coordinator.data.get("system_config", 0)

    # Add Circuit 1 if heating or cooling is enabled
    if system_config & (MASK_CIRCUIT1_HEATING | MASK_CIRCUIT1_COOLING):
        entities.append(HitachiYutakiClimate(coordinator, 1))

    # Add Circuit 2 if heating or cooling is enabled
    if system_config & (MASK_CIRCUIT2_HEATING | MASK_CIRCUIT2_COOLING):
        entities.append(HitachiYutakiClimate(coordinator, 2))

    async_add_entities(entities)


class HitachiYutakiClimate(HitachiYutakiEntity, ClimateEntity):
    """Representation of a Hitachi Yutaki Climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: HitachiYutakiDataUpdateCoordinator,
        circuit_number: int,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self.circuit_number = circuit_number
        self._attr_unique_id = f"{self.coordinator.unique_id}_circuit{circuit_number}_climate"
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
        )
        self._attr_preset_modes = [PRESET_COMFORT, PRESET_ECO]
        self._attr_hvac_modes = [HVACMode.OFF]

        # Add supported HVAC modes based on system configuration
        system_config = coordinator.data.get("system_config", 0)
        circuit_heating = MASK_CIRCUIT1_HEATING if circuit_number == 1 else MASK_CIRCUIT2_HEATING
        circuit_cooling = MASK_CIRCUIT1_COOLING if circuit_number == 1 else MASK_CIRCUIT2_COOLING

        if system_config & circuit_heating:
            self._attr_hvac_modes.append(HVACMode.HEAT)
        if system_config & circuit_cooling:
            self._attr_hvac_modes.append(HVACMode.COOL)
        if len(self._attr_hvac_modes) > 2:  # If both heating and cooling supported
            self._attr_hvac_modes.append(HVACMode.AUTO)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data.get(f"circuit{self.circuit_number}_current_temp")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self.coordinator.data.get(f"circuit{self.circuit_number}_target_temp")

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if not self.coordinator.data.get(f"circuit{self.circuit_number}_power"):
            return HVACMode.OFF

        unit_mode = self.coordinator.data.get("unit_mode")
        if unit_mode == OPERATION_MODE_HEAT:
            return HVACMode.HEAT
        elif unit_mode == OPERATION_MODE_COOL:
            return HVACMode.COOL
        return HVACMode.AUTO

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current HVAC action."""
        if not self.coordinator.data.get(f"circuit{self.circuit_number}_power"):
            return HVACAction.OFF

        system_status = self.coordinator.data.get("system_status", 0)
        if system_status & MASK_DEFROST:
            return HVACAction.DEFROST

        # You'll need to implement logic to determine if the system is actively
        # heating/cooling or idle based on your system's behavior
        # This is a simplified example:
        current_temp = self.current_temperature
        target_temp = self.target_temperature
        if current_temp is None or target_temp is None:
            return HVACAction.IDLE

        mode = self.hvac_mode
        if mode == HVACMode.HEAT and current_temp < target_temp:
            return HVACAction.HEATING
        elif mode == HVACMode.COOL and current_temp > target_temp:
            return HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        if self.coordinator.data.get(f"circuit{self.circuit_number}_eco_mode"):
            return PRESET_ECO
        return PRESET_COMFORT

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            await self.coordinator.client.write_register(
                f"circuit{self.circuit_number}_target_temp",
                int(temperature * 10)
            )
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.client.write_register(
                f"circuit{self.circuit_number}_power",
                0
            )
        else:
            # First ensure the circuit is powered on
            await self.coordinator.client.write_register(
                f"circuit{self.circuit_number}_power",
                1
            )

            # Then set the operation mode if needed
            if hvac_mode != HVACMode.OFF:
                mode_map = {
                    HVACMode.HEAT: OPERATION_MODE_HEAT,
                    HVACMode.COOL: OPERATION_MODE_COOL,
                    HVACMode.AUTO: OPERATION_MODE_AUTO,
                }
                await self.coordinator.client.write_register(
                    "unit_mode",
                    mode_map[hvac_mode]
                )

        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.coordinator.client.write_register(
            f"circuit{self.circuit_number}_eco_mode",
            1 if preset_mode == PRESET_ECO else 0
        )
        await self.coordinator.async_request_refresh()
