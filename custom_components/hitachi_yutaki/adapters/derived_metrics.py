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

from ..adapters.calculators.electrical import ElectricalPowerCalculatorAdapter
from ..adapters.calculators.thermal import (
    thermal_power_calculator_cooling_wrapper,
    thermal_power_calculator_heating_wrapper,
)
from ..adapters.providers.operation_mode import resolve_operation_mode
from ..adapters.storage.in_memory import InMemoryStorage
from ..const import CONF_WATER_INLET_TEMP_ENTITY, CONF_WATER_OUTLET_TEMP_ENTITY
from ..domain.models.cop import COPInput
from ..domain.models.operation import MODE_COOLING, MODE_DHW, MODE_HEATING, MODE_POOL
from ..domain.services.cop import (
    COP_MEASUREMENTS_HISTORY_SIZE,
    COP_MEASUREMENTS_PERIOD,
    COPService,
    EnergyAccumulator,
)
from ..domain.services.defrost_guard import DefrostGuard
from ..domain.services.thermal import ThermalEnergyAccumulator, ThermalPowerService

_LOGGER = logging.getLogger(__name__)


class DerivedMetricsAdapter:
    """Computes derived metrics and injects them into the coordinator data dict."""

    def __init__(
        self,
        hass: Any,
        config_entry: Any,
        power_supply: str,
        has_cooling: bool = False,
        has_dhw: bool = False,
        has_pool: bool = False,
        supports_secondary_compressor: bool = False,
    ) -> None:
        """Initialize the adapter with domain services."""
        self._hass = hass
        self._config_entry = config_entry
        self._config_entry_data: dict[str, Any] = (
            config_entry.data if hasattr(config_entry, "data") else config_entry
        )
        self._has_cooling = has_cooling
        self._supports_secondary_compressor = supports_secondary_compressor

        # Defrost guard (shared across all derived metrics)
        self.defrost_guard = DefrostGuard()

        # Thermal power service
        self._thermal_service = ThermalPowerService(
            accumulator=ThermalEnergyAccumulator()
        )

        # Electrical power calculator
        self._electrical_calculator = ElectricalPowerCalculatorAdapter(
            hass=hass,
            config_entry=config_entry,
            power_supply=power_supply,
        )

        # COP services (one per mode)
        self._cop_services: dict[str, COPService] = {}
        self._init_cop_services(has_cooling, has_dhw, has_pool)

    def _make_cop_service(
        self, thermal_calculator: Any, expected_mode: str
    ) -> COPService:
        """Create a COPService instance for a given mode."""
        storage: InMemoryStorage = InMemoryStorage(
            max_len=COP_MEASUREMENTS_HISTORY_SIZE
        )
        accumulator = EnergyAccumulator(storage=storage, period=COP_MEASUREMENTS_PERIOD)
        return COPService(
            accumulator=accumulator,
            thermal_calculator=thermal_calculator,
            electrical_calculator=self._electrical_calculator,
            expected_mode=expected_mode,
        )

    def _init_cop_services(
        self, has_cooling: bool, has_dhw: bool, has_pool: bool
    ) -> None:
        """Initialize COP services for the configured modes."""
        self._cop_services = {}
        self._cop_services["cop_heating"] = self._make_cop_service(
            thermal_power_calculator_heating_wrapper, MODE_HEATING
        )
        if has_cooling:
            self._cop_services["cop_cooling"] = self._make_cop_service(
                thermal_power_calculator_cooling_wrapper, MODE_COOLING
            )
        if has_dhw:
            self._cop_services["cop_dhw"] = self._make_cop_service(
                thermal_power_calculator_heating_wrapper, MODE_DHW
            )
        if has_pool:
            self._cop_services["cop_pool"] = self._make_cop_service(
                thermal_power_calculator_heating_wrapper, MODE_POOL
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
        self._update_cop(data)

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

    def _get_hvac_action(self, data: dict[str, Any]) -> str | None:
        """Detect the current HVAC action from unit mode and temperatures."""
        unit_mode = data.get("unit_mode")
        if unit_mode == 1:
            return "heating"
        elif unit_mode == 0:
            return "cooling"
        elif unit_mode == 2:
            # AUTO: detect from temperature delta
            inlet = data.get("water_inlet_temp")
            outlet = data.get("water_outlet_temp")
            if inlet is not None and outlet is not None:
                delta = outlet - inlet
                if delta > 0.5:
                    return "heating"
                elif delta < -0.5:
                    return "cooling"
        return None

    def _update_cop(self, data: dict[str, Any]) -> None:
        """Compute electrical power and COP for all configured modes."""
        # Electrical power
        current = data.get("compressor_current")
        if current is not None and current > 0:
            data["electrical_power"] = round(self._electrical_calculator(current), 3)
        else:
            data["electrical_power"] = 0

        # Build COP input
        hvac_action = self._get_hvac_action(data)
        operation_mode = resolve_operation_mode(data.get("operation_state"))

        cop_input = COPInput(
            water_inlet_temp=self._get_temperature(
                data, CONF_WATER_INLET_TEMP_ENTITY, "water_inlet_temp"
            ),
            water_outlet_temp=self._get_temperature(
                data, CONF_WATER_OUTLET_TEMP_ENTITY, "water_outlet_temp"
            ),
            water_flow=data.get("water_flow"),
            compressor_current=data.get("compressor_current"),
            compressor_frequency=data.get("compressor_frequency"),
            secondary_compressor_current=(
                data.get("secondary_compressor_current")
                if self._supports_secondary_compressor
                else None
            ),
            secondary_compressor_frequency=(
                data.get("secondary_compressor_frequency")
                if self._supports_secondary_compressor
                else None
            ),
            hvac_action=hvac_action,
            operation_mode=operation_mode,
        )

        # Update each COP service
        for key, service in self._cop_services.items():
            if self.defrost_guard.is_data_reliable:
                service.update(cop_input)

            data[key] = service.get_value()
            quality = service.get_quality()
            data[f"{key}_quality"] = quality.quality
            data[f"{key}_measurements"] = quality.measurements
            data[f"{key}_time_span_minutes"] = quality.time_span_minutes

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
