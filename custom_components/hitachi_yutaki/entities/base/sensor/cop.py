"""COP (Coefficient of Performance) sensor for Hitachi Yutaki."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.components.climate import HVACMode
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import StateType

from ....adapters.calculators.electrical import ElectricalPowerCalculatorAdapter
from ....adapters.calculators.thermal import (
    thermal_power_calculator_cooling_wrapper,
    thermal_power_calculator_heating_wrapper,
    thermal_power_calculator_wrapper,
)
from ....adapters.providers.operation_mode import (
    get_accepted_operation_states,
    resolve_operation_mode,
)
from ....adapters.storage.in_memory import InMemoryStorage
from ....adapters.storage.recorder_rehydrate import async_replay_cop_history
from ....const import (
    CONF_POWER_SUPPLY,
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
    DEFAULT_POWER_SUPPLY,
)
from ....coordinator import HitachiYutakiDataCoordinator
from ....domain.models.operation import MODE_COOLING, MODE_DHW, MODE_HEATING, MODE_POOL
from ....domain.services.cop import (
    COP_MEASUREMENTS_HISTORY_SIZE,
    COP_MEASUREMENTS_INTERVAL,
    COP_MEASUREMENTS_PERIOD,
    COPInput,
    COPService,
    EnergyAccumulator,
)
from .base import HitachiYutakiSensor, HitachiYutakiSensorEntityDescription

_LOGGER = logging.getLogger(__name__)


class HitachiYutakiCOPSensor(HitachiYutakiSensor):
    """Sensor for COP (Coefficient of Performance) measurements."""

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiSensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the COP sensor."""
        super().__init__(coordinator, description, device_info)

        storage = InMemoryStorage(max_len=COP_MEASUREMENTS_HISTORY_SIZE)
        accumulator = EnergyAccumulator(
            storage=storage, period=COP_MEASUREMENTS_PERIOD
        )
        electrical_calculator = ElectricalPowerCalculatorAdapter(
            hass=coordinator.hass,
            config_entry=coordinator.config_entry,
            power_supply=coordinator.config_entry.data.get(
                CONF_POWER_SUPPLY, DEFAULT_POWER_SUPPLY
            ),
        )

        thermal_calculator, expected_mode = self._get_cop_calculator_and_mode(
            description.key
        )

        self._cop_service = COPService(
            accumulator=accumulator,
            thermal_calculator=thermal_calculator,
            electrical_calculator=electrical_calculator,
            expected_mode=expected_mode,
        )
        self._cop_electrical_calculator = electrical_calculator
        self._cop_expected_mode = expected_mode

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        await self._async_rehydrate_cop_history()

    @staticmethod
    def _get_cop_calculator_and_mode(key: str) -> tuple[Callable, str | None]:
        """Get the thermal calculator and expected mode for a COP sensor.

        Args:
            key: The sensor entity key (e.g., "cop_heating", "cop_cooling")

        Returns:
            Tuple of (thermal_calculator, expected_mode)

        """
        cop_calculators = {
            "cop_heating": (thermal_power_calculator_heating_wrapper, MODE_HEATING),
            "cop_cooling": (thermal_power_calculator_cooling_wrapper, MODE_COOLING),
            # DHW uses heating calculator (outlet > inlet) with operation_state filtering
            "cop_dhw": (thermal_power_calculator_heating_wrapper, MODE_DHW),
            # Pool uses heating calculator (outlet > inlet) with operation_state filtering
            "cop_pool": (thermal_power_calculator_heating_wrapper, MODE_POOL),
        }
        # Fallback to absolute value calculator with no mode filtering
        return cop_calculators.get(key, (thermal_power_calculator_wrapper, None))

    def _get_cop_input(self) -> COPInput | None:
        """Get COP input data or None if coordinator data is missing."""
        if self.coordinator.data is None:
            return None

        # Get secondary compressor data if supported
        has_secondary = self.coordinator.profile.supports_secondary_compressor

        # Determine current HVAC action from the unit mode
        hvac_action = self._get_hvac_action()

        # Map Modbus operation_state to domain-level mode
        operation_state_raw = self.coordinator.data.get("operation_state")
        operation_mode = resolve_operation_mode(operation_state_raw)

        return COPInput(
            water_inlet_temp=self._get_temperature(
                CONF_WATER_INLET_TEMP_ENTITY, "water_inlet_temp"
            ),
            water_outlet_temp=self._get_temperature(
                CONF_WATER_OUTLET_TEMP_ENTITY, "water_outlet_temp"
            ),
            water_flow=self.coordinator.data.get("water_flow"),
            compressor_current=self.coordinator.data.get("compressor_current"),
            compressor_frequency=self.coordinator.data.get("compressor_frequency"),
            secondary_compressor_current=(
                self.coordinator.data.get("secondary_compressor_current")
                if has_secondary
                else None
            ),
            secondary_compressor_frequency=(
                self.coordinator.data.get("secondary_compressor_frequency")
                if has_secondary
                else None
            ),
            hvac_action=hvac_action,
            operation_mode=operation_mode,
        )

    def _get_hvac_action(self) -> str | None:
        """Get the current HVAC action (heating or cooling).

        Returns:
            "heating", "cooling", or None if unknown

        """
        # Get unit mode from API
        unit_mode = self.coordinator.api_client.get_unit_mode()
        if unit_mode is None:
            return None

        if unit_mode == HVACMode.HEAT:
            return "heating"
        elif unit_mode == HVACMode.COOL:
            return "cooling"
        elif unit_mode == HVACMode.AUTO:
            # In AUTO mode, determine based on temperature delta
            return self._detect_mode_from_temperatures()

        return None

    def _detect_mode_from_temperatures(self) -> str | None:
        """Detect heating/cooling mode from water temperature delta.

        In AUTO mode, we infer the mode from whether we're adding or
        removing heat from the water.

        Returns:
            "heating" if outlet > inlet, "cooling" if outlet < inlet, None otherwise

        """
        water_inlet = self._get_temperature(
            CONF_WATER_INLET_TEMP_ENTITY, "water_inlet_temp"
        )
        water_outlet = self._get_temperature(
            CONF_WATER_OUTLET_TEMP_ENTITY, "water_outlet_temp"
        )

        if water_inlet is None or water_outlet is None:
            return None

        delta_t = water_outlet - water_inlet

        # Use a small threshold to avoid noise
        if delta_t > 0.5:
            return "heating"
        elif delta_t < -0.5:
            return "cooling"

        return None

    def _get_cop_value(self) -> StateType:
        """Get COP value using the COP sensor service."""
        if not self.coordinator.defrost_guard.is_data_reliable:
            return self._cop_service.get_value()

        cop_input = self._get_cop_input()
        if cop_input is None:
            return None

        # Update the sensor with new data
        self._cop_service.update(cop_input)

        # Return the current value
        return self._cop_service.get_value()

    def _get_cop_attributes(self) -> dict[str, Any]:
        """Get attributes for COP sensors."""
        quality = self._cop_service.get_quality()
        return {
            "quality": quality.quality,
            "measurements": quality.measurements,
            "time_span_minutes": quality.time_span_minutes,
        }

    async def _async_rehydrate_cop_history(self) -> None:
        """Replay Recorder data to rebuild the COP measurement buffer."""
        try:
            entity_map = await self._async_build_cop_entity_map()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to build COP Recorder entity map for %s", self)
            return

        required_keys = {
            "water_inlet_temp",
            "water_outlet_temp",
            "water_flow",
            "compressor_current",
            "compressor_frequency",
        }
        missing = [key for key in required_keys if key not in entity_map]
        if missing:
            _LOGGER.debug(
                "Skipping COP rehydration for %s, missing Recorder entities: %s",
                self.entity_id,
                missing,
            )
            return

        # Compute accepted operation_state values for mode filtering
        accepted_states: set[str] | None = None
        if self._cop_expected_mode:
            accepted_states = get_accepted_operation_states(self._cop_expected_mode)

        try:
            measurements = await async_replay_cop_history(
                hass=self.hass,
                entity_ids=entity_map,
                thermal_calculator=thermal_power_calculator_wrapper,
                electrical_calculator=self._cop_electrical_calculator,
                window=COP_MEASUREMENTS_PERIOD,
                measurement_interval=COP_MEASUREMENTS_INTERVAL,
                max_measurements=COP_MEASUREMENTS_HISTORY_SIZE,
                accepted_operation_states=accepted_states,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Failed to replay Recorder history for COP sensor %s", self.entity_id
            )
            return

        if not measurements:
            _LOGGER.debug(
                "No Recorder measurements available for COP sensor %s", self.entity_id
            )
            return

        self._cop_service.preload_measurements(measurements)
        _LOGGER.debug(
            "Rehydrated %s COP measurements for %s",
            len(measurements),
            self.entity_id,
        )

    async def _async_build_cop_entity_map(self) -> dict[str, str]:
        """Resolve Recorder entity_ids needed for COP rehydration.

        Preference order:
        1. User-provided entities (configured via options)
        2. Built-in sensors registered by this integration (entity registry lookup)
        """

        mapping: dict[str, str] = {}
        entry = self.coordinator.config_entry

        inlet_entity = entry.data.get(CONF_WATER_INLET_TEMP_ENTITY)
        if inlet_entity:
            mapping["water_inlet_temp"] = inlet_entity
        else:
            resolved = self._resolve_entity_id("sensor", "water_inlet_temp")
            if resolved:
                mapping["water_inlet_temp"] = resolved

        outlet_entity = entry.data.get(CONF_WATER_OUTLET_TEMP_ENTITY)
        if outlet_entity:
            mapping["water_outlet_temp"] = outlet_entity
        else:
            resolved = self._resolve_entity_id("sensor", "water_outlet_temp")
            if resolved:
                mapping["water_outlet_temp"] = resolved

        for key in (
            "water_flow",
            "compressor_current",
            "compressor_frequency",
            "operation_state",
        ):
            resolved = self._resolve_entity_id("sensor", key)
            if resolved:
                mapping[key] = resolved

        if self.coordinator.profile.supports_secondary_compressor:
            for key in (
                "secondary_compressor_current",
                "secondary_compressor_frequency",
            ):
                resolved = self._resolve_entity_id("sensor", key)
                if resolved:
                    mapping[key] = resolved

        return mapping

    @property
    def native_value(self) -> StateType:
        """Return the COP value."""
        if self.coordinator.data is None:
            return None
        return self._get_cop_value()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return COP quality attributes."""
        return self._get_cop_attributes()
