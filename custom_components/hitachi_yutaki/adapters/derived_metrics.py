"""DerivedMetricsAdapter — enriches coordinator data with computed metrics.

Orchestrates domain services to compute thermal power, electrical power,
COP, and compressor timing from raw gateway data. Results are injected
into the data dict so entities and telemetry see enriched data.

Lives in the adapters layer: may access HA (for external entity readings)
and delegates computation to domain services.
"""

from __future__ import annotations

import logging
from typing import Any

from ..adapters.providers.operation_mode import resolve_operation_mode
from ..const import CONF_WATER_INLET_TEMP_ENTITY, CONF_WATER_OUTLET_TEMP_ENTITY
from ..domain.services.defrost_guard import DefrostGuard
from ..domain.services.thermal import ThermalEnergyAccumulator, ThermalPowerService

_LOGGER = logging.getLogger(__name__)


class DerivedMetricsAdapter:
    """Computes derived metrics and injects them into the coordinator data dict."""

    def __init__(
        self,
        hass: Any,
        config_entry_data: dict[str, Any],
        power_supply: str,
        has_cooling: bool = False,
        supports_secondary_compressor: bool = False,
    ) -> None:
        """Initialize the adapter with domain services."""
        self._hass = hass
        self._config_entry_data = config_entry_data
        self._has_cooling = has_cooling

        # Defrost guard (shared across all derived metrics)
        self.defrost_guard = DefrostGuard()

        # Thermal power service
        self._thermal_service = ThermalPowerService(
            accumulator=ThermalEnergyAccumulator()
        )

    def update(self, data: dict[str, Any]) -> None:
        """Enrich data dict with all derived metrics."""
        # Update defrost guard first
        water_inlet = data.get("water_inlet_temp")
        water_outlet = data.get("water_outlet_temp")
        delta_t = (
            (water_outlet - water_inlet)
            if water_inlet is not None and water_outlet is not None
            else None
        )
        is_defrosting = data.get("is_defrosting", False)
        self.defrost_guard.update(is_defrosting=is_defrosting, delta_t=delta_t)

        self._update_thermal(data)

    def _get_temperature(
        self, data: dict[str, Any], config_key: str, fallback_key: str
    ) -> float | None:
        """Get temperature from configured external entity or coordinator data."""
        if self._hass is not None:
            entity_id = self._config_entry_data.get(config_key)
            if entity_id:
                state = self._hass.states.get(entity_id)
                if state and state.state not in (None, "unknown", "unavailable"):
                    try:
                        return float(state.state)
                    except ValueError:
                        pass
        return data.get(fallback_key)

    def _update_thermal(self, data: dict[str, Any]) -> None:
        """Compute thermal power and energy, inject into data."""
        water_inlet = self._get_temperature(
            data, CONF_WATER_INLET_TEMP_ENTITY, "water_inlet_temp"
        )
        water_outlet = self._get_temperature(
            data, CONF_WATER_OUTLET_TEMP_ENTITY, "water_outlet_temp"
        )
        water_flow = data.get("water_flow")

        if not self.defrost_guard.is_data_reliable:
            water_inlet = None
            water_outlet = None

        operation_state_raw = data.get("operation_state")
        operation_mode = resolve_operation_mode(operation_state_raw)

        self._thermal_service.update(
            water_inlet_temp=water_inlet,
            water_outlet_temp=water_outlet,
            water_flow=water_flow,
            compressor_frequency=data.get("compressor_frequency"),
            operation_mode=operation_mode,
        )

        data["thermal_power_heating"] = round(
            self._thermal_service.get_heating_power(), 2
        )
        if self._has_cooling:
            data["thermal_power_cooling"] = round(
                self._thermal_service.get_cooling_power(), 2
            )

        data["thermal_energy_heating_daily"] = round(
            self._thermal_service.get_daily_heating_energy(), 2
        )
        data["thermal_energy_heating_total"] = round(
            self._thermal_service.get_total_heating_energy(), 2
        )
        if self._has_cooling:
            data["thermal_energy_cooling_daily"] = round(
                self._thermal_service.get_daily_cooling_energy(), 2
            )
            data["thermal_energy_cooling_total"] = round(
                self._thermal_service.get_total_cooling_energy(), 2
            )

    def restore_thermal_energy(self, key: str, value: float) -> None:
        """Restore thermal energy state from HA last state cache."""
        restore_map = {
            "thermal_energy_heating_daily": self._thermal_service.restore_daily_heating_energy,
            "thermal_energy_heating_total": self._thermal_service.restore_total_heating_energy,
            "thermal_energy_cooling_daily": self._thermal_service.restore_daily_cooling_energy,
            "thermal_energy_cooling_total": self._thermal_service.restore_total_cooling_energy,
        }
        restore_fn = restore_map.get(key)
        if restore_fn:
            restore_fn(value)
