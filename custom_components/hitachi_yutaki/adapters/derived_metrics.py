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
    thermal_power_calculator_wrapper,
)
from ..adapters.providers.operation_mode import (
    get_accepted_operation_states,
    resolve_operation_mode,
)
from ..adapters.storage.in_memory import InMemoryStorage
from ..const import (
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
    DOMAIN,
)
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
from ..domain.services.timing import CompressorHistory, CompressorTimingService

_LOGGER = logging.getLogger(__name__)

COMPRESSOR_HISTORY_SIZE = 100


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

        # Compressor timing services
        storage_t = InMemoryStorage(max_len=COMPRESSOR_HISTORY_SIZE)
        history_t = CompressorHistory(
            storage=storage_t, max_history=COMPRESSOR_HISTORY_SIZE
        )
        self._primary_timing = CompressorTimingService(history=history_t)

        self._secondary_timing: CompressorTimingService | None = None
        if supports_secondary_compressor:
            storage_t2 = InMemoryStorage(max_len=COMPRESSOR_HISTORY_SIZE)
            history_t2 = CompressorHistory(
                storage=storage_t2, max_history=COMPRESSOR_HISTORY_SIZE
            )
            self._secondary_timing = CompressorTimingService(history=history_t2)

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
        self._update_timing(data)

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

    async def async_rehydrate_cop(self) -> None:
        """Replay Recorder data to rebuild COP measurement buffers."""
        if self._hass is None:
            return

        from homeassistant.helpers import entity_registry as er  # noqa: PLC0415

        from ..adapters.storage.recorder_rehydrate import (  # noqa: PLC0415
            async_replay_cop_history,
        )
        from ..domain.services.cop import (  # noqa: PLC0415
            COP_MEASUREMENTS_HISTORY_SIZE,
            COP_MEASUREMENTS_INTERVAL,
            COP_MEASUREMENTS_PERIOD,
        )

        registry = er.async_get(self._hass)
        entry_id = self._config_entry.entry_id

        # Build entity map (resolve entity_ids from unique_ids)
        entity_map: dict[str, str] = {}

        # Check for user-configured external entities first
        inlet_entity = self._config_entry_data.get(CONF_WATER_INLET_TEMP_ENTITY)
        if inlet_entity:
            entity_map["water_inlet_temp"] = inlet_entity
        else:
            eid = registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry_id}_water_inlet_temp"
            )
            if eid:
                entity_map["water_inlet_temp"] = eid

        outlet_entity = self._config_entry_data.get(CONF_WATER_OUTLET_TEMP_ENTITY)
        if outlet_entity:
            entity_map["water_outlet_temp"] = outlet_entity
        else:
            eid = registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry_id}_water_outlet_temp"
            )
            if eid:
                entity_map["water_outlet_temp"] = eid

        for key in (
            "water_flow",
            "compressor_current",
            "compressor_frequency",
            "operation_state",
        ):
            eid = registry.async_get_entity_id("sensor", DOMAIN, f"{entry_id}_{key}")
            if eid:
                entity_map[key] = eid

        if self._supports_secondary_compressor:
            for key in (
                "secondary_compressor_current",
                "secondary_compressor_frequency",
            ):
                eid = registry.async_get_entity_id(
                    "sensor", DOMAIN, f"{entry_id}_{key}"
                )
                if eid:
                    entity_map[key] = eid

        # Rehydrate each COP service
        for cop_key, service in self._cop_services.items():
            accepted_states: set[str] | None = None
            if service._expected_mode:
                accepted_states = get_accepted_operation_states(service._expected_mode)

            try:
                measurements = await async_replay_cop_history(
                    hass=self._hass,
                    entity_ids=entity_map,
                    thermal_calculator=thermal_power_calculator_wrapper,
                    electrical_calculator=self._electrical_calculator,
                    window=COP_MEASUREMENTS_PERIOD,
                    measurement_interval=COP_MEASUREMENTS_INTERVAL,
                    max_measurements=COP_MEASUREMENTS_HISTORY_SIZE,
                    accepted_operation_states=accepted_states,
                )
                if measurements:
                    service.preload_measurements(measurements)
                    _LOGGER.debug(
                        "Rehydrated %d COP measurements for %s",
                        len(measurements),
                        cop_key,
                    )
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Failed to rehydrate COP for %s", cop_key, exc_info=True)

    def _update_timing(self, data: dict[str, Any]) -> None:
        """Update compressor timing and inject into data."""
        # Primary compressor
        self._primary_timing.update(data.get("compressor_frequency"))
        timing = self._primary_timing.get_timing()
        data["compressor_cycle_time"] = timing.cycle_time
        data["compressor_runtime"] = timing.runtime
        data["compressor_resttime"] = timing.resttime

        # Secondary compressor
        if self._secondary_timing is not None:
            self._secondary_timing.update(data.get("secondary_compressor_frequency"))
            sec_timing = self._secondary_timing.get_timing()
            data["secondary_compressor_cycle_time"] = sec_timing.cycle_time
            data["secondary_compressor_runtime"] = sec_timing.runtime
            data["secondary_compressor_resttime"] = sec_timing.resttime

    async def async_rehydrate_timing(self) -> None:
        """Replay Recorder data to rebuild compressor timing history."""
        if self._hass is None:
            return

        from datetime import timedelta  # noqa: PLC0415

        from homeassistant.helpers import entity_registry as er  # noqa: PLC0415

        from ..adapters.storage.recorder_rehydrate import (  # noqa: PLC0415
            async_replay_compressor_states,
        )

        LOOKBACK = timedelta(hours=6)
        registry = er.async_get(self._hass)
        entry_id = self._config_entry.entry_id

        # Primary compressor
        entity_id = registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{entry_id}_compressor_running"
        )
        if entity_id:
            try:
                states = await async_replay_compressor_states(
                    hass=self._hass,
                    entity_id=entity_id,
                    window=LOOKBACK,
                    max_states=COMPRESSOR_HISTORY_SIZE,
                )
                if states:
                    self._primary_timing.preload_states(states)
                    _LOGGER.debug("Rehydrated %d compressor timing states", len(states))
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Failed to rehydrate primary compressor timing", exc_info=True
                )

        # Secondary compressor
        if self._secondary_timing is not None:
            entity_id = registry.async_get_entity_id(
                "binary_sensor",
                DOMAIN,
                f"{entry_id}_secondary_compressor_running",
            )
            if entity_id:
                try:
                    states = await async_replay_compressor_states(
                        hass=self._hass,
                        entity_id=entity_id,
                        window=LOOKBACK,
                        max_states=COMPRESSOR_HISTORY_SIZE,
                    )
                    if states:
                        self._secondary_timing.preload_states(states)
                        _LOGGER.debug(
                            "Rehydrated %d secondary compressor timing states",
                            len(states),
                        )
                except Exception:  # noqa: BLE001
                    _LOGGER.debug(
                        "Failed to rehydrate secondary compressor timing",
                        exc_info=True,
                    )
