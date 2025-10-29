"""Electrical power calculator adapter for Home Assistant."""

from __future__ import annotations

from contextlib import suppress

from ...domain.models.electrical import ElectricalPowerInput
from ...domain.ports.calculators import ElectricalPowerCalculator
from ...domain.services.electrical import calculate_electrical_power


class ElectricalPowerCalculatorAdapter:
    """Adapter to fetch electrical data from HA and calculate power.

    This adapter bridges Home Assistant entities with the isolated electrical service.
    It retrieves data from configured entities and passes them to the pure calculation.
    """

    def __init__(self, hass, config_entry, power_supply: str) -> None:
        """Initialize the adapter.

        Args:
            hass: Home Assistant instance
            config_entry: Configuration entry
            power_supply: Power supply type ("single" or "three")

        """
        self._hass = hass
        self._config_entry = config_entry
        self._is_three_phase = power_supply == "three"

    def _get_float_from_entity(self, config_key: str) -> float | None:
        """Get float value from a configured entity.

        Args:
            config_key: Configuration key for the entity

        Returns:
            Float value or None if unavailable

        """
        entity_id = self._config_entry.data.get(config_key)
        if not entity_id:
            return None

        state = self._hass.states.get(entity_id)
        if not state or state.state in (None, "unknown", "unavailable"):
            return None

        with suppress(ValueError):
            return float(state.state)
        return None

    def __call__(self, current: float) -> float:
        """Calculate electrical power in kW.

        Fetches optional measurements from HA entities and delegates to
        the pure calculation function.

        Args:
            current: Electrical current in Amperes

        Returns:
            Electrical power in kW

        """
        # Delegate to pure calculation function
        return calculate_electrical_power(
            ElectricalPowerInput(
                current=current,
                measured_power=self._get_float_from_entity("power_entity"),
                voltage=self._get_float_from_entity("voltage_entity"),
                is_three_phase=self._is_three_phase,
            )
        )


# Type alias for protocol compliance
ElectricalPowerCalculatorImpl: type[ElectricalPowerCalculator] = (
    ElectricalPowerCalculatorAdapter
)
