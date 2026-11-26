"""Base climate entity for Hitachi Yutaki integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
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

from ...adapters.circuit import get_circuit_activity
from ...const import (
    CIRCUIT_IDS,
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    PRESET_COMFORT,
)
from ...coordinator import HitachiYutakiDataCoordinator
from ...domain.models.circuit import CircuitActivity
from .command import CommandStep, async_send_command

_ACTIVITY_TO_HA = {
    CircuitActivity.OFF: HVACAction.OFF,
    CircuitActivity.IDLE: HVACAction.IDLE,
    CircuitActivity.HEATING: HVACAction.HEATING,
    CircuitActivity.COOLING: HVACAction.COOLING,
    CircuitActivity.DEFROSTING: HVACAction.DEFROSTING,
}


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
        multi_circuit: bool = False,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._circuit_id = circuit_id
        self._multi_circuit = multi_circuit
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
        if multi_circuit:
            # Multi-circuit: only on/off, global mode is controlled via
            # control_unit_operation_mode entity
            self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
        else:
            # Single circuit: full mode control
            self._attr_hvac_modes = [HVACMode.OFF]
            if (
                coordinator.has_circuit(circuit_id, CIRCUIT_MODE_HEATING)
                and "heat" in coordinator.api_client.supported_unit_modes
            ):
                self._attr_hvac_modes.append(HVACMode.HEAT)
            if (
                coordinator.has_circuit(circuit_id, CIRCUIT_MODE_COOLING)
                and "cool" in coordinator.api_client.supported_unit_modes
            ):
                self._attr_hvac_modes.append(HVACMode.COOL)
            if (
                len(self._attr_hvac_modes) > 2
                and "auto" in coordinator.api_client.supported_unit_modes
            ):
                self._attr_hvac_modes.append(HVACMode.AUTO)

        # Set available presets — ECO requires eco_mode register
        self._attr_preset_modes = [PRESET_COMFORT]
        if coordinator.api_client.can_write(f"circuit{circuit_id}_eco_mode"):
            self._attr_preset_modes.append(PRESET_ECO)

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

        if self._multi_circuit:
            return HVACMode.HEAT_COOL

        return self.coordinator.api_client.get_unit_mode()

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        if self.coordinator.data is None:
            return None
        activity = get_circuit_activity(self.coordinator.api_client, self._circuit_id)
        return _ACTIVITY_TO_HA.get(activity)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self.coordinator.data is None:
            return None

        is_eco = self.coordinator.api_client.get_circuit_eco_mode(self._circuit_id)
        if is_eco is None:
            return None

        return PRESET_ECO if is_eco else PRESET_COMFORT

    def _hvac_mode_steps(self, hvac_mode: HVACMode) -> list[CommandStep]:
        """Return the writes that put the circuit in ``hvac_mode``.

        Off only cuts the circuit power. Any other mode powers the circuit on,
        and a single circuit also sets the global unit mode; with two circuits
        the global mode belongs to the operating-mode select.
        """
        api = self.coordinator.api_client
        circuit_id = self._circuit_id
        if hvac_mode == HVACMode.OFF:
            return [
                CommandStep(
                    "circuit_power", lambda: api.set_circuit_power(circuit_id, False)
                )
            ]
        steps = [
            CommandStep(
                "circuit_power", lambda: api.set_circuit_power(circuit_id, True)
            )
        ]
        if not self._multi_circuit:
            steps.append(CommandStep("unit_mode", lambda: api.set_unit_mode(hvac_mode)))
        return steps

    async def _async_command(self, *steps: CommandStep) -> None:
        """Send ``steps`` as one command, raising if the gateway refuses one."""
        await async_send_command(self.coordinator, self.entity_id, *steps)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature, and the HVAC mode when one is given.

        The ``climate.set_temperature`` action may carry an ``hvac_mode``: it is
        applied first, through the same writes as ``async_set_hvac_mode``.
        """
        temperature = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        steps = [] if hvac_mode is None else self._hvac_mode_steps(hvac_mode)
        if temperature is not None:
            api = self.coordinator.api_client
            circuit_id = self._circuit_id
            steps.append(
                CommandStep(
                    "target_temperature",
                    lambda: api.set_circuit_target_temperature(circuit_id, temperature),
                )
            )
        if steps:
            await self._async_command(*steps)

    async def async_set_room_temperature(self, **kwargs) -> None:
        """Set the measured room temperature (Modbus thermostat mode)."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        api = self.coordinator.api_client
        await self._async_command(
            CommandStep(
                "room_temperature",
                lambda: api.set_circuit_room_temperature(self._circuit_id, temperature),
            )
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self._async_command(*self._hvac_mode_steps(hvac_mode))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in self.preset_modes:
            return

        api = self.coordinator.api_client
        await self._async_command(
            CommandStep(
                "eco_mode",
                lambda: api.set_circuit_eco_mode(
                    self._circuit_id, preset_mode == PRESET_ECO
                ),
            )
        )

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        if self._multi_circuit:
            await self.async_set_hvac_mode(HVACMode.HEAT_COOL)
        else:
            await self.async_set_hvac_mode(
                HVACMode.HEAT
                if HVACMode.HEAT in self._attr_hvac_modes
                else HVACMode.COOL
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
