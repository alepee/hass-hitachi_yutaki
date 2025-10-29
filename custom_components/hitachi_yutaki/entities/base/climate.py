"""Base climate entity for Hitachi Yutaki integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.climate import (
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...const import (
    CIRCUIT_IDS,
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    PRESET_COMFORT,
)
from ...coordinator import HitachiYutakiDataCoordinator


@dataclass
class HitachiYutakiClimateEntityDescription(ClimateEntityDescription):
    """Class describing Hitachi Yutaki climate entities."""

    key: str
    translation_key: str


class HitachiYutakiClimate(
    CoordinatorEntity[HitachiYutakiDataCoordinator], ClimateEntity
):
    """Representation of a Hitachi Yutaki Climate."""

    entity_description: HitachiYutakiClimateEntityDescription

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiClimateEntityDescription,
        device_info: DeviceInfo,
        circuit_id: CIRCUIT_IDS,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._circuit_id = circuit_id
        self._register_prefix = f"circuit{circuit_id}"
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{self._register_prefix}_climate"
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
        climate_overrides = coordinator.profile.entity_overrides.get("climate", {})
        self._attr_min_temp = climate_overrides.get("min_temp", 5.0)
        self._attr_max_temp = climate_overrides.get("max_temp", 35.0)
        self._attr_target_temperature_step = climate_overrides.get("temp_step", 0.5)
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        # Set available modes
        self._attr_hvac_modes = [HVACMode.OFF]
        if (
            coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING)
            if circuit_id == CIRCUIT_PRIMARY_ID
            else coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING)
        ):
            self._attr_hvac_modes.append(HVACMode.HEAT)
        if (
            coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING)
            if circuit_id == CIRCUIT_PRIMARY_ID
            else coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING)
        ):
            self._attr_hvac_modes.append(HVACMode.COOL)
        if len(self._attr_hvac_modes) > 2:  # If both heating and cooling are available
            self._attr_hvac_modes.append(HVACMode.AUTO)

        # Set available presets
        self._attr_preset_modes = [PRESET_COMFORT, PRESET_ECO]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data is None:
            return None

        return self.coordinator.api_client.get_circuit_current_temperature(
            self._circuit_id
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.coordinator.data is None:
            return None

        return self.coordinator.api_client.get_circuit_target_temperature(
            self._circuit_id
        )

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation mode."""
        if self.coordinator.data is None:
            return None

        power = self.coordinator.api_client.get_circuit_power(self._circuit_id)
        if not power:
            return HVACMode.OFF

        return self.coordinator.api_client.get_unit_mode()

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        if self.hvac_mode == HVACAction.OFF:
            return HVACAction.OFF

        if self.coordinator.data is None:
            return None

        # Check if in defrost mode
        if self.coordinator.api_client.is_defrosting:
            return HVACAction.DEFROSTING

        # Check if compressor is running
        if not self.coordinator.api_client.is_compressor_running:
            return HVACAction.IDLE

        hvac_mode = self.coordinator.api_client.get_unit_mode()
        if hvac_mode == HVACMode.COOL:
            return HVACAction.COOLING
        elif hvac_mode == HVACMode.HEAT:
            return HVACAction.HEATING

        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self.coordinator.data is None:
            return None

        is_eco = self.coordinator.api_client.get_circuit_eco_mode(self._circuit_id)
        if is_eco is None:
            return None

        return PRESET_ECO if is_eco else PRESET_COMFORT

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        await self.coordinator.api_client.set_circuit_target_temperature(
            self._circuit_id, temperature
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.api_client.set_circuit_power(self._circuit_id, False)
            await self.coordinator.async_request_refresh()
            return

        # Ensure circuit is powered on
        await self.coordinator.api_client.set_circuit_power(self._circuit_id, True)

        # Set unit mode
        await self.coordinator.api_client.set_unit_mode(hvac_mode)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in self.preset_modes:
            return

        await self.coordinator.api_client.set_circuit_eco_mode(
            self._circuit_id, preset_mode == PRESET_ECO
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.async_set_hvac_mode(
            HVACMode.HEAT if HVACMode.HEAT in self._attr_hvac_modes else HVACMode.COOL
        )

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_toggle(self) -> None:
        """Toggle the entity."""
        if self.hvac_mode == HVACMode.OFF:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        raise NotImplementedError("Humidity control not supported")

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        raise NotImplementedError("Fan mode control not supported")

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        raise NotImplementedError("Swing mode control not supported")

    async def async_turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        raise NotImplementedError("Auxiliary heat control not supported")

    async def async_turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        raise NotImplementedError("Auxiliary heat control not supported")
