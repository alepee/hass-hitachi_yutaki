"""Base sensor entity and description for Hitachi Yutaki."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...adapters.calculators.electrical import ElectricalPowerCalculatorAdapter
from ...adapters.calculators.thermal import thermal_power_calculator_wrapper
from ...adapters.storage.in_memory import InMemoryStorage
from ...adapters.storage.recorder_rehydrate import (
    async_replay_compressor_states,
    async_replay_cop_history,
)
from ...const import (
    CONF_POWER_SUPPLY,
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
    DEFAULT_POWER_SUPPLY,
    DEVICE_TYPES,
    DOMAIN,
)
from ...coordinator import HitachiYutakiDataCoordinator
from ...domain.services.cop import (
    COP_MEASUREMENTS_HISTORY_SIZE,
    COP_MEASUREMENTS_INTERVAL,
    COP_MEASUREMENTS_PERIOD,
    COPInput,
    COPService,
    EnergyAccumulator,
)
from ...domain.services.thermal import ThermalEnergyAccumulator, ThermalPowerService
from ...domain.services.timing import CompressorHistory, CompressorTimingService

_LOGGER = logging.getLogger(__name__)

# This is a placeholder for a future configuration option
COMPRESSOR_HISTORY_SIZE = 100
# Look back a few hours in the Recorder history to rebuild compressor cycles.
COMPRESSOR_HISTORY_LOOKBACK = timedelta(hours=6)


@dataclass
class HitachiYutakiSensorEntityDescription(SensorEntityDescription):
    """Class describing Hitachi Yutaki sensor entities."""

    key: str
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    native_unit_of_measurement: str | None = None
    entity_category: EntityCategory | None = None
    icon: str | None = None
    entity_registry_enabled_default: bool = True
    translation_key: str | None = None
    description: str | None = None
    fallback_translation_key: str | None = None
    condition: Callable[[HitachiYutakiDataCoordinator], bool] | None = None
    value_fn: Callable[[HitachiYutakiDataCoordinator], StateType] | None = None


def _create_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    descriptions: tuple[HitachiYutakiSensorEntityDescription, ...],
    device_type: DEVICE_TYPES,
) -> list[HitachiYutakiSensor]:
    """Create sensors for a specific device type.

    Args:
        coordinator: The data coordinator
        entry_id: The config entry ID
        descriptions: Sensor descriptions to create
        device_type: Device type identifier (e.g., DEVICE_GATEWAY)

    Returns:
        List of created sensor entities

    """
    return [
        HitachiYutakiSensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry_id}_{device_type}")},
            ),
        )
        for description in descriptions
        if description.condition is None or description.condition(coordinator)
    ]


class HitachiYutakiSensor(
    CoordinatorEntity[HitachiYutakiDataCoordinator], SensorEntity, RestoreEntity
):
    """Representation of a Hitachi Yutaki Sensor."""

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiSensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

        # Initialize services based on entity key
        if description.key.startswith("cop_"):
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

            self._cop_service = COPService(
                accumulator=accumulator,
                thermal_calculator=thermal_power_calculator_wrapper,
                electrical_calculator=electrical_calculator,
            )
            self._cop_electrical_calculator = electrical_calculator

        elif "thermal_energy" in description.key or "thermal_power" in description.key:
            accumulator = ThermalEnergyAccumulator()
            self._thermal_service = ThermalPowerService(accumulator=accumulator)

        elif "compressor" in description.key and "time" in description.key:
            storage = InMemoryStorage(max_len=COMPRESSOR_HISTORY_SIZE)
            history = CompressorHistory(
                storage=storage, max_history=COMPRESSOR_HISTORY_SIZE
            )
            self._timing_service = CompressorTimingService(history=history)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        await self._async_restore_thermal_energy()

        if hasattr(self, "_cop_service"):
            await self._async_rehydrate_cop_history()

        if hasattr(self, "_timing_service"):
            await self._async_rehydrate_compressor_history()

    def _is_same_day_reset(self, state) -> bool:
        """Check if the last reset was today."""
        last_reset_str = state.attributes.get("last_reset")
        if not last_reset_str:
            return False
        with suppress(ValueError):
            last_reset = datetime.fromisoformat(last_reset_str).date()
            return last_reset == datetime.now().date()
        return False

    def _get_temperature(self, entity_key: str, fallback_key: str) -> float | None:
        """Get temperature from a configured entity, falling back to coordinator data."""
        entity_id = self.coordinator.config_entry.data.get(entity_key)
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state and state.state not in (None, "unknown", "unavailable"):
                with suppress(ValueError):
                    return float(state.state)
        return self.coordinator.data.get(fallback_key)

    def _get_thermal_data(self) -> tuple[float, float, float] | None:
        """Get thermal data (inlet, outlet, flow) or None if any is missing."""
        if self.coordinator.data is None:
            return None

        water_inlet = self._get_temperature(
            CONF_WATER_INLET_TEMP_ENTITY, "water_inlet_temp"
        )
        water_outlet = self._get_temperature(
            CONF_WATER_OUTLET_TEMP_ENTITY, "water_outlet_temp"
        )
        water_flow = self.coordinator.data.get("water_flow")

        if None in (water_inlet, water_outlet, water_flow):
            return None

        return water_inlet, water_outlet, water_flow  # type: ignore

    def _get_thermal_result(self):
        """Get thermal result or None if data is missing.

        Helper to avoid duplication in extra_state_attributes.
        """
        thermal_data = self._get_thermal_data()
        if thermal_data is None:
            return None

        water_inlet, water_outlet, water_flow = thermal_data
        return self._thermal_service.get_result(water_inlet, water_outlet, water_flow)

    def _get_cop_input(self) -> COPInput | None:
        """Get COP input data or None if coordinator data is missing."""
        if self.coordinator.data is None:
            return None

        # Get secondary compressor data if supported
        has_secondary = self.coordinator.profile.supports_secondary_compressor

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
        )

    async def _async_restore_thermal_energy(self) -> None:
        """Restore thermal energy state from the Recorder/last state cache."""
        if not hasattr(self, "_thermal_service"):
            return

        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        with suppress(ValueError):
            energy_value = float(last_state.state)
            if self.entity_description.key == "total_thermal_energy":
                self._thermal_service.restore_total_energy(energy_value)
            elif self.entity_description.key == "daily_thermal_energy":
                if self._is_same_day_reset(last_state):
                    self._thermal_service.restore_daily_energy(energy_value)

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

        try:
            measurements = await async_replay_cop_history(
                hass=self.hass,
                entity_ids=entity_map,
                thermal_calculator=thermal_power_calculator_wrapper,
                electrical_calculator=self._cop_electrical_calculator,
                window=COP_MEASUREMENTS_PERIOD,
                measurement_interval=COP_MEASUREMENTS_INTERVAL,
                max_measurements=COP_MEASUREMENTS_HISTORY_SIZE,
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

        for key in ("water_flow", "compressor_current", "compressor_frequency"):
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

    def _resolve_entity_id(self, platform_domain: str, key: str) -> str | None:
        """Return the entity_id registered for the provided (domain, unique_id)."""
        registry = er.async_get(self.hass)
        unique_id = f"{self.coordinator.config_entry.entry_id}_{key}"
        return registry.async_get_entity_id(platform_domain, DOMAIN, unique_id)

    async def _async_rehydrate_compressor_history(self) -> None:
        """Replay Recorder data to rebuild compressor timing statistics."""
        entity_key = (
            "secondary_compressor_running"
            if "secondary" in self.entity_description.key
            else "compressor_running"
        )
        entity_id = self._resolve_entity_id("binary_sensor", entity_key)
        if not entity_id:
            _LOGGER.debug(
                "Skipping compressor history replay for %s, entity %s missing",
                self.entity_id,
                entity_key,
            )
            return

        try:
            states = await async_replay_compressor_states(
                hass=self.hass,
                entity_id=entity_id,
                window=COMPRESSOR_HISTORY_LOOKBACK,
                max_states=COMPRESSOR_HISTORY_SIZE,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Failed to replay compressor Recorder history for %s", self.entity_id
            )
            return

        if not states:
            _LOGGER.debug(
                "No compressor Recorder history found for %s", self.entity_id
            )
            return

        self._timing_service.preload_states(states)
        _LOGGER.debug(
            "Rehydrated %s compressor states for %s",
            len(states),
            self.entity_id,
        )

    async def async_update_timing(self) -> None:
        """Update timing values from history."""
        if hasattr(self, "_timing_service"):
            frequency = self.coordinator.data.get(
                "secondary_compressor_frequency"
                if "secondary" in self.entity_description.key
                else "compressor_frequency"
            )
            self._timing_service.update(frequency)

    def _get_cop_value(self) -> StateType:
        """Get COP value using the COP sensor service."""
        cop_input = self._get_cop_input()
        if cop_input is None:
            return None

        # Update the sensor with new data
        self._cop_service.update(cop_input)

        # Return the current value
        return self._cop_service.get_value()

    def _update_thermal_energy(self) -> None:
        """Update thermal energy using the thermal sensor service."""
        thermal_data = self._get_thermal_data()
        if thermal_data is None:
            return

        water_inlet, water_outlet, water_flow = thermal_data
        self._thermal_service.update(
            water_inlet_temp=water_inlet,
            water_outlet_temp=water_outlet,
            water_flow=water_flow,
            compressor_frequency=self.coordinator.data.get("compressor_frequency"),
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        # Delegate to specific methods for complex sensors
        if self.entity_description.key.startswith("cop_"):
            return self._get_cop_value()

        if (
            "thermal_energy" in self.entity_description.key
            or "thermal_power" in self.entity_description.key
        ):
            self._update_thermal_energy()
            if self.entity_description.key == "thermal_power":
                return self._thermal_service.get_power()
            elif self.entity_description.key == "daily_thermal_energy":
                return self._thermal_service.get_daily_energy()
            else:  # total_thermal_energy
                return self._thermal_service.get_total_energy()

        if (
            "compressor" in self.entity_description.key
            and "time" in self.entity_description.key
        ):
            timing = self._timing_service.get_timing()
            if "cycle_time" in self.entity_description.key:
                return timing.cycle_time
            elif "runtime" in self.entity_description.key:
                return timing.runtime
            elif "resttime" in self.entity_description.key:
                return timing.resttime

        # For simple sensors, use value_fn if provided
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self.coordinator)

        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    def _get_cop_attributes(self) -> dict[str, Any]:
        """Get attributes for COP sensors."""
        quality = self._cop_service.get_quality()
        return {
            "quality": quality.quality,
            "measurements": quality.measurements,
            "time_span_minutes": quality.time_span_minutes,
        }

    def _get_thermal_power_attributes(self) -> dict[str, Any] | None:
        """Get attributes for thermal_power sensor."""
        result = self._get_thermal_result()
        if result is None:
            return None

        # Get water flow for attributes
        water_flow = self.coordinator.data.get("water_flow", 0)

        return {
            "last_update": result.last_update.isoformat(),
            "delta_t": round(result.delta_t, 2),
            "water_flow": round(water_flow, 2),
            "units": {"delta_t": "°C", "water_flow": "m³/h"},
        }

    def _get_daily_thermal_energy_attributes(self) -> dict[str, Any] | None:
        """Get attributes for daily_thermal_energy sensor."""
        result = self._get_thermal_result()
        if result is None or result.daily_start_time is None:
            return None

        time_span = (
            datetime.now() - result.daily_start_time
        ).total_seconds() / 3600  # hours
        avg_power = result.daily_energy / time_span if time_span > 0 else 0

        return {
            "last_reset": result.last_reset_date.isoformat(),
            "start_time": result.daily_start_time.isoformat(),
            "average_power": round(avg_power, 2),
            "time_span_hours": round(time_span, 1),
            "units": {"average_power": "kW", "time_span": "hours"},
        }

    def _get_total_thermal_energy_attributes(self) -> dict[str, Any] | None:
        """Get attributes for total_thermal_energy sensor."""
        result = self._get_thermal_result()
        if result is None or result.last_update is None:
            return None

        start_date = result.last_update.date()
        start_datetime = datetime.combine(start_date, datetime.min.time())
        time_span_seconds = (datetime.now() - start_datetime).total_seconds()
        time_span_hours = time_span_seconds / 3600

        # Calculate average power: total energy / time in hours
        avg_power = result.total_energy / time_span_hours if time_span_hours > 0 else 0

        return {
            "start_date": start_date.isoformat(),
            "average_power": round(avg_power, 2),
            "time_span_days": round(time_span_hours / 24, 1),
            "units": {"average_power": "kW", "time_span": "days"},
        }

    def _get_alarm_attributes(self) -> dict[str, Any] | None:
        """Get attributes for alarm sensor."""
        if self.coordinator.data is None or not self.entity_description.value_fn:
            return None
        value = self.entity_description.value_fn(self.coordinator)
        if value is not None and value != 0:
            return {"code": value}
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        key = self.entity_description.key

        # Dispatch attributes based on sensor key
        if key == "alarm":
            return self._get_alarm_attributes()
        elif key.startswith("cop_"):
            return self._get_cop_attributes()
        elif key == "thermal_power":
            return self._get_thermal_power_attributes()
        elif key == "daily_thermal_energy":
            return self._get_daily_thermal_energy_attributes()
        elif key == "total_thermal_energy":
            return self._get_total_thermal_energy_attributes()

        return None
