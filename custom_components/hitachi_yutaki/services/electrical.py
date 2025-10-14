"""Electrical power calculation logic, dependent on Home Assistant."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Configuration constants for electrical power calculation
CONF_POWER_ENTITY = "power_entity"
CONF_VOLTAGE_ENTITY = "voltage_entity"
POWER_FACTOR = 0.9
THREE_PHASE_FACTOR = 1.732
VOLTAGE_SINGLE_PHASE = 230.0
VOLTAGE_THREE_PHASE = 400.0


class ElectricalPowerService:
    """Service to calculate electrical power, with HA dependencies."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, power_supply: str
    ) -> None:
        """Initialize the electrical power service."""
        self._hass = hass
        self._config_entry = config_entry
        self._power_supply = power_supply

    def calculate(self, current: float) -> float:
        """Calculate electrical power in kW."""
        # Check if a dedicated power entity is configured
        power_entity_id = self._config_entry.data.get(CONF_POWER_ENTITY)
        if power_entity_id:
            power_state = self._hass.states.get(power_entity_id)
            if power_state and power_state.state not in (
                None,
                "unknown",
                "unavailable",
            ):
                try:
                    power_value = float(power_state.state)
                    # Simple heuristic to convert W to kW if necessary
                    return power_value / 1000 if power_value > 50 else power_value
                except ValueError:
                    _LOGGER.warning(
                        "Could not convert power value '%s' from entity %s to float",
                        power_state.state,
                        power_entity_id,
                    )

        # Get voltage from entity if configured, otherwise use default
        default_voltage = (
            VOLTAGE_SINGLE_PHASE
            if self._power_supply == "single"
            else VOLTAGE_THREE_PHASE
        )
        voltage_entity_id = self._config_entry.data.get(CONF_VOLTAGE_ENTITY)
        voltage = default_voltage

        if voltage_entity_id:
            voltage_state = self._hass.states.get(voltage_entity_id)
            if voltage_state and voltage_state.state not in (
                None,
                "unknown",
                "unavailable",
            ):
                try:
                    voltage = float(voltage_state.state)
                except ValueError:
                    _LOGGER.warning(
                        "Could not convert voltage value '%s' from entity %s to float, using default %.1f V",
                        voltage_state.state,
                        voltage_entity_id,
                        default_voltage,
                    )

        if self._power_supply == "single":
            # Single phase: P = U * I * cos φ
            power = (voltage * current * POWER_FACTOR) / 1000
        else:
            # Three phase: P = U * I * cos φ * √3
            power = (voltage * current * POWER_FACTOR * THREE_PHASE_FACTOR) / 1000

        return power
