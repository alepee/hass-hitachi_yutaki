"""Sensor platform for Hitachi Yutaki integration."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from time import time
from typing import Any, Final, NamedTuple

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_POWER_ENTITY,
    CONF_VOLTAGE_ENTITY,
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
    COP_MEASUREMENTS_HISTORY_SIZE,
    COP_MEASUREMENTS_INTERVAL,
    COP_MEASUREMENTS_PERIOD,
    COP_MIN_MEASUREMENTS,
    COP_MIN_TIME_SPAN,
    COP_OPTIMAL_MEASUREMENTS,
    COP_OPTIMAL_TIME_SPAN,
    DEVICE_CONTROL_UNIT,
    DEVICE_DHW,
    DEVICE_GATEWAY,
    DEVICE_POOL,
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_SECONDARY_COMPRESSOR,
    DOMAIN,
    MASK_COMPRESSOR,
    OPERATION_STATE_MAP,
    POWER_FACTOR,
    SYSTEM_STATE_MAP,
    THREE_PHASE_FACTOR,
    VOLTAGE_SINGLE_PHASE,
    VOLTAGE_THREE_PHASE,
    WATER_FLOW_TO_KGS,
    WATER_SPECIFIC_HEAT,
)
from .coordinator import HitachiYutakiDataCoordinator

_LOGGER = logging.getLogger(__name__)


class PowerMeasurement(NamedTuple):
    """Class to store a power measurement with its timestamp."""

    timestamp: datetime
    thermal_power: float
    electrical_power: float


class EnergyAccumulator:
    """Class to accumulate energy over time for COP calculation."""

    def __init__(self, period: timedelta) -> None:
        """Initialize the accumulator."""
        self.period = period
        self.measurements = deque(maxlen=COP_MEASUREMENTS_HISTORY_SIZE)

    def add_measurement(self, thermal_power: float, electrical_power: float) -> None:
        """Add a power measurement to the accumulator."""
        current_time = datetime.now()
        self.measurements.append(
            PowerMeasurement(current_time, thermal_power, electrical_power)
        )

        # Remove measurements older than the period
        cutoff_time = current_time - self.period
        while self.measurements and self.measurements[0].timestamp < cutoff_time:
            self.measurements.popleft()

    def get_cop(self) -> float | None:
        """Calculate COP from accumulated energy."""
        if not self.measurements:
            return None

        # Calculate total energy by integrating power over time
        thermal_energy = 0.0
        electrical_energy = 0.0

        for i in range(len(self.measurements) - 1):
            interval_in_seconds = (
                self.measurements[i + 1].timestamp - self.measurements[i].timestamp
            ).total_seconds()
            interval_in_hours = interval_in_seconds / 3600  # hours
            avg_thermal_power = (
                self.measurements[i].thermal_power
                + self.measurements[i + 1].thermal_power
            ) / 2
            avg_electrical_power = (
                self.measurements[i].electrical_power
                + self.measurements[i + 1].electrical_power
            ) / 2

            thermal_energy += avg_thermal_power * interval_in_hours
            electrical_energy += avg_electrical_power * interval_in_hours

            _LOGGER.debug(
                "Interval %d: %d seconds, Thermal: %.2f kW -> %.2f kW (avg: %.2f kW), Electrical: %.2f kW -> %.2f kW (avg: %.2f kW)",
                i,
                interval_in_seconds,
                self.measurements[i].thermal_power,
                self.measurements[i + 1].thermal_power,
                avg_thermal_power,
                self.measurements[i].electrical_power,
                self.measurements[i + 1].electrical_power,
                avg_electrical_power,
            )

        if electrical_energy <= 0:
            return None

        # Validate energy values (reasonable ranges for residential heat pump)
        if thermal_energy < 0.01 or thermal_energy > 100.0:
            _LOGGER.warning(
                "Accumulated thermal energy out of reasonable range: %.2f kWh",
                thermal_energy,
            )
            return None

        if electrical_energy < 0.01 or electrical_energy > 50.0:
            _LOGGER.warning(
                "Accumulated electrical energy out of reasonable range: %.2f kWh",
                electrical_energy,
            )
            return None

        cop_value = thermal_energy / electrical_energy

        # Validate final COP value (reasonable range for heat pump)
        if cop_value < 0.5 or cop_value > 8.0:
            _LOGGER.warning(
                "Calculated COP out of reasonable range: %.2f (thermal: %.2f kWh, electrical: %.2f kWh)",
                cop_value,
                thermal_energy,
                electrical_energy,
            )
            return None

        _LOGGER.debug(
            "Total energy over %d measurements: Thermal: %.2f kWh, Electrical: %.2f kWh, COP: %.2f",
            len(self.measurements),
            thermal_energy,
            electrical_energy,
            cop_value,
        )

        return cop_value


class CompressorHistory:
    """Class to track compressor history."""

    def __init__(self, max_history: int = 100) -> None:
        """Initialize the history."""
        self.max_history = max_history
        self.states: list[tuple[datetime, bool]] = []
        self._cycles: list[float] = []  # minutes
        self._run_times: list[float] = []  # minutes
        self._rest_times: list[float] = []  # minutes

    def add_state(self, is_running: bool) -> None:
        """Add a new state to history."""
        now = datetime.now()

        # If we have a previous state
        if self.states:
            last_time, last_state = self.states[-1]

            # Only add if state changed
            if last_state != is_running:
                duration = (now - last_time).total_seconds() / 60  # Convert to minutes

                # Calculate times based on the state change
                if is_running:  # Changing from off to on
                    if len(self.states) >= 2:  # We have a complete cycle
                        cycle_start = next(
                            (
                                time
                                for time, state in reversed(self.states[:-1])
                                if state
                            ),  # Find last running state
                            None,
                        )
                        if cycle_start:
                            cycle_time = (now - cycle_start).total_seconds() / 60
                            self._cycles.append(cycle_time)
                    self._rest_times.append(duration)
                else:  # Changing from on to off
                    self._run_times.append(duration)

                # Add the new state
                self.states.append((now, is_running))

                # Trim history if needed
                if len(self.states) > self.max_history:
                    self.states.pop(0)

                # Trim timing lists
                if len(self._cycles) > self.max_history:
                    self._cycles.pop(0)
                if len(self._run_times) > self.max_history:
                    self._run_times.pop(0)
                if len(self._rest_times) > self.max_history:
                    self._rest_times.pop(0)
        else:
            # First state
            self.states.append((now, is_running))

    def get_average_times(self) -> tuple[float | None, float | None, float | None]:
        """Get average cycle, run and rest times."""
        avg_cycle = sum(self._cycles) / len(self._cycles) if self._cycles else None
        avg_run = (
            sum(self._run_times) / len(self._run_times) if self._run_times else None
        )
        avg_rest = (
            sum(self._rest_times) / len(self._rest_times) if self._rest_times else None
        )
        return avg_cycle, avg_run, avg_rest

    def clear(self) -> None:
        """Clear all history."""
        self.states.clear()
        self._cycles.clear()
        self._run_times.clear()
        self._rest_times.clear()


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

    register_key: str | None = None
    translation_key: str | None = None
    description: str | None = None
    fallback_translation_key: str | None = None
    condition: Callable[[HitachiYutakiDataCoordinator], bool] | None = None
    value_fn: Callable[[Any, HitachiYutakiDataCoordinator], Any] | None = None


GATEWAY_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="system_state",
        translation_key="system_state",
        description="System state",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:state-machine",
        register_key="system_state",
        value_fn=lambda value, _: SYSTEM_STATE_MAP.get(value, "unknown"),
    ),
)

TEMPERATURE_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="outdoor_temp",
        translation_key="outdoor_temp",
        description="Outdoor ambient temperature measurement",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="outdoor_temp",
        value_fn=lambda value, coordinator: coordinator.convert_temperature(value),
    ),
    HitachiYutakiSensorEntityDescription(
        key="water_inlet_temp",
        translation_key="water_inlet_temp",
        description="Water inlet temperature measurement",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="water_inlet_temp",
        value_fn=lambda value, coordinator: coordinator.convert_temperature(value),
    ),
    HitachiYutakiSensorEntityDescription(
        key="water_outlet_temp",
        translation_key="water_outlet_temp",
        description="Water outlet temperature measurement",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="water_outlet_temp",
        value_fn=lambda value, coordinator: coordinator.convert_temperature(value),
    ),
    HitachiYutakiSensorEntityDescription(
        key="water_target_temp",
        translation_key="water_target_temp",
        description="Target water temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="water_target_temp",
        value_fn=lambda value, coordinator: coordinator.convert_temperature(value),
    ),
)

DHW_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = ()

POOL_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="pool_current_temp",
        translation_key="pool_current_temperature",
        description="Current temperature of the pool",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="pool_current_temp",
        value_fn=lambda value, coordinator: coordinator.convert_temperature(value),
    ),
)

CONTROL_UNIT_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="water_flow",
        translation_key="water_flow",
        description="Current water flow rate through the system",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        register_key="water_flow",
        value_fn=lambda value, coordinator: coordinator.convert_water_flow(value),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="pump_speed",
        translation_key="pump_speed",
        description="Current speed of the water circulation pump",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        register_key="pump_speed",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="power_consumption",
        translation_key="power_consumption",
        description="Total electrical energy consumed by the unit",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        register_key="power_consumption",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="alarm_code",
        translation_key="alarm_code",
        description="Alarm code",
        device_class=None,
        state_class=None,
        register_key="alarm_code",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="operation_state",
        translation_key="operation_state",
        description="Current operation state of the heat pump",
        register_key="operation_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:state-machine",
        value_fn=lambda value,
        _: f"operation_state_{OPERATION_STATE_MAP.get(value, 'unknown')}",
    ),
)

PERFORMANCE_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="cop_heating",
        translation_key="cop_heating",
        description="Coefficient of Performance for Space Heating",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:heat-pump",
        condition=lambda c: c.has_heating_circuit1() or c.has_heating_circuit2(),
    ),
    HitachiYutakiSensorEntityDescription(
        key="cop_cooling",
        translation_key="cop_cooling",
        description="Coefficient of Performance for Space Cooling",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:heat-pump-outline",
        condition=lambda c: c.has_cooling_circuit1() or c.has_cooling_circuit2(),
    ),
    HitachiYutakiSensorEntityDescription(
        key="cop_dhw",
        translation_key="cop_dhw",
        description="Coefficient of Performance for Domestic Hot Water",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:water-boiler",
        condition=lambda c: c.has_dhw(),
    ),
    HitachiYutakiSensorEntityDescription(
        key="cop_pool",
        translation_key="cop_pool",
        description="Coefficient of Performance for Pool Heating",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:pool",
        condition=lambda c: c.has_pool(),
    ),
)

THERMAL_ENERGY_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="thermal_power",
        translation_key="thermal_power",
        description="Current thermal power output",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:heat-wave",
    ),
    HitachiYutakiSensorEntityDescription(
        key="daily_thermal_energy",
        translation_key="daily_thermal_energy",
        description="Daily thermal energy production (resets at midnight)",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:heat-wave",
    ),
    HitachiYutakiSensorEntityDescription(
        key="total_thermal_energy",
        translation_key="total_thermal_energy",
        description="Total thermal energy production",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:heat-wave",
    ),
)

PRIMARY_COMPRESSOR_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="compressor_frequency",
        translation_key="compressor_frequency",
        description="Current operating frequency of the compressor",
        icon="mdi:sine-wave",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        register_key="compressor_frequency",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="compressor_current",
        translation_key="compressor_current",
        description="Current electrical consumption of the compressor",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        register_key="compressor_current",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="compressor_tg_gas_temp",
        translation_key="compressor_tg_gas_temp",
        description="Gas temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="compressor_tg_gas_temp",
        value_fn=lambda value, coordinator: coordinator.convert_temperature(value),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="compressor_ti_liquid_temp",
        translation_key="compressor_ti_liquid_temp",
        description="Liquid temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="compressor_ti_liquid_temp",
        value_fn=lambda value, coordinator: coordinator.convert_temperature(value),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="compressor_td_discharge_temp",
        translation_key="compressor_td_discharge_temp",
        description="Discharge temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="compressor_td_discharge_temp",
        value_fn=lambda value, coordinator: coordinator.convert_temperature(value),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="compressor_te_evaporator_temp",
        translation_key="compressor_te_evaporator_temp",
        description="Evaporator temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="compressor_te_evaporator_temp",
        value_fn=lambda value, coordinator: coordinator.convert_temperature(value),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="compressor_evi_indoor_expansion_valve_opening",
        translation_key="compressor_evi_indoor_expansion_valve_opening",
        description="Indoor expansion valve opening",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        register_key="compressor_evi_indoor_expansion_valve_opening",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="compressor_evo_outdoor_expansion_valve_opening",
        translation_key="compressor_evo_outdoor_expansion_valve_opening",
        description="Outdoor expansion valve opening",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        register_key="compressor_evo_outdoor_expansion_valve_opening",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="compressor_cycle_time",
        translation_key="compressor_cycle_time",
        description="Average time between compressor starts",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="min",
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-outline",
    ),
    HitachiYutakiSensorEntityDescription(
        key="compressor_runtime",
        translation_key="compressor_runtime",
        description="Average compressor runtime per cycle",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="min",
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-play-outline",
    ),
    HitachiYutakiSensorEntityDescription(
        key="compressor_resttime",
        translation_key="compressor_resttime",
        description="Average compressor rest time between cycles",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="min",
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-stop-outline",
    ),
)

SECONDARY_COMPRESSOR_SENSORS: Final[
    tuple[HitachiYutakiSensorEntityDescription, ...]
] = (
    HitachiYutakiSensorEntityDescription(
        key="r134a_discharge_temp",
        translation_key="r134a_discharge_temp",
        description="Temperature of the R134a refrigerant at compressor discharge",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="r134a_discharge_temp",
        value_fn=lambda value, coordinator: coordinator.convert_temperature(value),
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="r134a_suction_temp",
        translation_key="r134a_suction_temp",
        description="Temperature of the R134a refrigerant at compressor suction",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="r134a_suction_temp",
        value_fn=lambda value, coordinator: coordinator.convert_temperature(value),
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="r134a_discharge_pressure",
        translation_key="r134a_discharge_pressure",
        description="Pressure of the R134a refrigerant at compressor discharge",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        register_key="r134a_discharge_pressure",
        value_fn=lambda value, coordinator: coordinator.convert_pressure(value),
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="r134a_suction_pressure",
        translation_key="r134a_suction_pressure",
        description="Pressure of the R134a refrigerant at compressor suction",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        register_key="r134a_suction_pressure",
        value_fn=lambda value, coordinator: coordinator.convert_pressure(value),
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="r134a_compressor_frequency",
        translation_key="r134a_compressor_frequency",
        description="Operating frequency of the R134a compressor",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        register_key="r134a_compressor_frequency",
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="r134a_compressor_current",
        translation_key="r134a_compressor_current",
        description="Electrical current drawn by the R134a compressor",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        register_key="r134a_compressor_current",
        value_fn=lambda value, coordinator: coordinator.convert_current(value),
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="r134a_cycle_time",
        translation_key="r134a_cycle_time",
        description="Average time between R134a compressor starts",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="min",
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-outline",
        condition=lambda c: c.is_s80_model(),
    ),
    HitachiYutakiSensorEntityDescription(
        key="r134a_runtime",
        translation_key="r134a_runtime",
        description="Average R134a compressor runtime per cycle",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="min",
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-play-outline",
        condition=lambda c: c.is_s80_model(),
    ),
    HitachiYutakiSensorEntityDescription(
        key="r134a_resttime",
        translation_key="r134a_resttime",
        description="Average R134a compressor rest time between cycles",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="min",
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-stop-outline",
        condition=lambda c: c.is_s80_model(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[HitachiYutakiSensor] = []

    # Add gateway sensors
    entities.extend(
        HitachiYutakiSensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_GATEWAY}")},
            ),
        )
        for description in GATEWAY_SENSORS
    )

    # Add temperature sensors (always added as they are basic measurements)
    entities.extend(
        HitachiYutakiSensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
            ),
        )
        for description in TEMPERATURE_SENSORS
    )

    if coordinator.has_dhw():
        entities.extend(
            HitachiYutakiSensor(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DHW}")},
                ),
            )
            for description in DHW_SENSORS
        )

    if coordinator.has_pool():
        entities.extend(
            HitachiYutakiSensor(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_POOL}")},
                ),
            )
            for description in POOL_SENSORS
        )

    # Add control unit sensors based on configuration
    for description in CONTROL_UNIT_SENSORS:
        # Skip DHW sensors if DHW is not configured
        if description.key == "dhw_temp" and not coordinator.has_dhw():
            continue
        if description.key == "dhw_target_temp" and not coordinator.has_dhw():
            continue

        entities.append(
            HitachiYutakiSensor(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
                ),
            )
        )

    # Add primary compressor sensors
    entities.extend(
        HitachiYutakiSensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_PRIMARY_COMPRESSOR}")},
            ),
        )
        for description in PRIMARY_COMPRESSOR_SENSORS
    )

    # Add secondary compressor sensors
    entities.extend(
        HitachiYutakiSensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={
                    (DOMAIN, f"{entry.entry_id}_{DEVICE_SECONDARY_COMPRESSOR}")
                },
            ),
        )
        for description in SECONDARY_COMPRESSOR_SENSORS
        if description.condition is None or description.condition(coordinator)
    )

    # Add performance sensors
    entities.extend(
        HitachiYutakiSensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
            ),
        )
        for description in PERFORMANCE_SENSORS
        if description.condition is None or description.condition(coordinator)
    )

    # Add thermal energy sensors
    entities.extend(
        HitachiYutakiSensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
            ),
        )
        for description in THERMAL_ENERGY_SENSORS
    )

    # Register entities with coordinator
    coordinator.entities.extend(entities)

    async_add_entities(entities)


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
        self._attr_unique_id = f"{entry_id}_{coordinator.slave}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True
        self._timing_values = {}

        # Initialize history for COPs
        if description.key in ("cop_heating", "cop_cooling", "cop_dhw", "cop_pool"):
            self._last_measurement = 0
            self._energy_accumulator = EnergyAccumulator(COP_MEASUREMENTS_PERIOD)

        # Initialize thermal energy tracking
        if description.key in (
            "thermal_power",
            "daily_thermal_energy",
            "total_thermal_energy",
        ):
            self._last_thermal_measurement = 0
            self._last_power = 0.0
            self._daily_energy = 0.0
            self._total_energy = 0.0
            self._last_reset = datetime.now().date()
            self._daily_start_time = 0

        # Initialize compressor history
        if description.key in (
            "compressor_cycle_time",
            "compressor_runtime",
            "compressor_resttime",
            "r134a_cycle_time",
            "r134a_runtime",
            "r134a_resttime",
        ):
            self._compressor_history = CompressorHistory()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        if last_state := await self.async_get_last_state():
            if self.entity_description.key == "total_thermal_energy":
                with suppress(ValueError):
                    self._total_energy = float(last_state.state)
                    _LOGGER.debug(
                        "Restored total thermal energy: %.2f kWh",
                        self._total_energy,
                    )
                if not hasattr(self, "_total_energy"):
                    self._total_energy = 0.0
                    _LOGGER.warning(
                        "Could not restore total thermal energy from state: %s",
                        last_state.state,
                    )
            elif self.entity_description.key == "daily_thermal_energy":
                # Only restore daily energy if it's from the same day
                last_reset = None
                if last_state.attributes.get("last_reset"):
                    with suppress(ValueError):
                        last_reset = datetime.fromisoformat(
                            last_state.attributes["last_reset"]
                        ).date()

                if last_reset == datetime.now().date():
                    with suppress(ValueError):
                        self._daily_energy = float(last_state.state)
                        self._last_reset = last_reset
                        if last_state.attributes.get("start_time"):
                            self._daily_start_time = datetime.fromisoformat(
                                last_state.attributes["start_time"]
                            ).timestamp()
                        _LOGGER.debug(
                            "Restored daily thermal energy: %.2f kWh",
                            self._daily_energy,
                        )
                    if not hasattr(self, "_daily_energy"):
                        self._daily_energy = 0.0
                        _LOGGER.warning(
                            "Could not restore daily thermal energy from state: %s",
                            last_state.state,
                        )

    def _get_temperature(self, register_key: str, entity_key: str) -> float | None:
        """Get temperature from entity if configured, otherwise from register."""
        # Try to get temperature from configured entity
        entity_id = self.coordinator.config_entry.data.get(entity_key)
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state and state.state not in (None, "unknown", "unavailable"):
                try:
                    return float(state.state)
                except ValueError:
                    pass

        if self.coordinator.data is None or not self.coordinator.last_update_success:
            return None

        # Fall back to register value
        value = self.coordinator.data.get(register_key)
        if value is not None:
            return self.coordinator.convert_temperature(value)
        return None

    def _calculate_electrical_power(self, current: float) -> float:
        """Calculate electrical power in kW based on current and power supply type."""
        # Check if power entity is configured
        power_entity_id = self.coordinator.config_entry.data.get(CONF_POWER_ENTITY)
        if power_entity_id:
            power_state = self.hass.states.get(power_entity_id)
            if power_state and power_state.state not in (
                None,
                "unknown",
                "unavailable",
            ):
                try:
                    return float(power_state.state) / 1000  # Convert W to kW
                except ValueError:
                    _LOGGER.warning(
                        "Could not convert power value '%s' from entity %s to float",
                        power_state.state,
                        power_entity_id,
                    )

        # Get voltage from entity if configured, otherwise use default
        default_voltage = (
            VOLTAGE_SINGLE_PHASE
            if self.coordinator.power_supply == "single"
            else VOLTAGE_THREE_PHASE
        )

        voltage_entity_id = self.coordinator.config_entry.data.get(CONF_VOLTAGE_ENTITY)
        if voltage_entity_id:
            voltage_state = self.hass.states.get(voltage_entity_id)
            if voltage_state and voltage_state.state not in (
                None,
                "unknown",
                "unavailable",
            ):
                try:
                    voltage = float(voltage_state.state)
                    _LOGGER.debug(
                        "Using voltage %.1f V from entity %s",
                        voltage,
                        voltage_entity_id,
                    )
                except ValueError:
                    voltage = default_voltage
                    _LOGGER.warning(
                        "Could not convert voltage value '%s' from entity %s to float, using default %.1f V",
                        voltage_state.state,
                        voltage_entity_id,
                        default_voltage,
                    )
            else:
                voltage = default_voltage
                _LOGGER.debug(
                    "Voltage entity %s not available, using default %.1f V",
                    voltage_entity_id,
                    default_voltage,
                )
        else:
            voltage = default_voltage
            _LOGGER.debug("Using default voltage %.1f V", default_voltage)

        if self.coordinator.power_supply == "single":
            # Single phase: P = U * I * cos φ
            power = (voltage * current * POWER_FACTOR) / 1000
            _LOGGER.debug(
                "Calculated single phase power: %.2f kW (%.1f V * %.1f A * %.2f)",
                power,
                voltage,
                current,
                POWER_FACTOR,
            )
            return power
        else:
            # Three phase: P = U * I * cos φ * √3
            power = (voltage * current * POWER_FACTOR * THREE_PHASE_FACTOR) / 1000
            _LOGGER.debug(
                "Calculated three phase power: %.2f kW (%.1f V * %.1f A * %.2f * %.2f)",
                power,
                voltage,
                current,
                POWER_FACTOR,
                THREE_PHASE_FACTOR,
            )
            return power

    def _calculate_cop_values(self) -> tuple[float | None, float | None]:
        """Calculate thermal and electrical power for COP."""
        if self.coordinator.data is None or not self.coordinator.last_update_success:
            return None, None

        # Check if compressor is running
        system_status = self.coordinator.data.get("system_status")
        if system_status is None or not bool(system_status & MASK_COMPRESSOR):
            _LOGGER.debug("Compressor not running, skipping COP calculation")
            return None, None

        # Get temperatures from entities if configured, otherwise from registers
        water_inlet = self._get_temperature(
            "water_inlet_temp", CONF_WATER_INLET_TEMP_ENTITY
        )
        water_outlet = self._get_temperature(
            "water_outlet_temp", CONF_WATER_OUTLET_TEMP_ENTITY
        )
        water_flow_raw = self.coordinator.data.get("water_flow")
        water_flow = self.coordinator.convert_water_flow(water_flow_raw)

        if None in (water_inlet, water_outlet, water_flow):
            _LOGGER.debug(
                "Missing values for COP calculation: inlet=%.1f°C, outlet=%.1f°C, flow=%s m³/h",
                water_inlet if water_inlet is not None else float("nan"),
                water_outlet if water_outlet is not None else float("nan"),
                water_flow if water_flow is not None else "None",
            )
            return None, None

        # Validate temperature values (reasonable range for heat pump operation)
        if (
            water_inlet < -10
            or water_inlet > 60
            or water_outlet < -10
            or water_outlet > 80
        ):
            _LOGGER.warning(
                "Temperature values out of reasonable range: inlet=%.1f°C, outlet=%.1f°C",
                water_inlet,
                water_outlet,
            )
            return None, None

        # Validate water flow (reasonable range for residential heat pump)
        if water_flow < 0.1 or water_flow > 10.0:
            _LOGGER.warning(
                "Water flow value out of reasonable range: %.2f m³/h", water_flow
            )
            return None, None

        # Convert water flow and calculate thermal power
        water_flow_kgs = water_flow * WATER_FLOW_TO_KGS
        delta_t = water_outlet - water_inlet

        # Validate temperature difference (reasonable range for heat pump operation)
        if abs(delta_t) < 0.5 or abs(delta_t) > 30:
            _LOGGER.warning(
                "Temperature difference out of reasonable range: %.1f K (inlet=%.1f°C, outlet=%.1f°C)",
                abs(delta_t),
                water_inlet,
                water_outlet,
            )
            return None, None

        thermal_power = abs(
            water_flow_kgs * WATER_SPECIFIC_HEAT * delta_t
        )  # Result is already in kW

        # Validate thermal power (reasonable range for residential heat pump)
        if thermal_power < 0.1 or thermal_power > 50.0:
            _LOGGER.warning(
                "Calculated thermal power out of reasonable range: %.2f kW",
                thermal_power,
            )
            return None, None

        _LOGGER.debug(
            "Thermal power calculation: %.2f kW (%.2f kg/s * %.2f kJ/kg·K * %.1f K) [flow=%.1f m³/h]",
            thermal_power,
            water_flow_kgs,
            WATER_SPECIFIC_HEAT,
            abs(delta_t),
            water_flow,
        )

        # Get electrical power from entity if configured
        power_entity_id = self.coordinator.config_entry.data.get(CONF_POWER_ENTITY)
        if power_entity_id:
            power_state = self.hass.states.get(power_entity_id)
            if power_state and power_state.state not in (
                None,
                "unknown",
                "unavailable",
            ):
                try:
                    power_value = float(power_state.state)

                    # Check unit from entity attributes first
                    unit_of_measurement = power_state.attributes.get(
                        "unit_of_measurement", ""
                    )

                    if unit_of_measurement in ["W", "watt", "watts"]:
                        electrical_power = power_value / 1000  # Convert W to kW
                        _LOGGER.debug(
                            "Power value %.2f W converted to %.3f kW (from unit_of_measurement)",
                            power_value,
                            electrical_power,
                        )
                    elif unit_of_measurement in ["kW", "kilowatt", "kilowatts"]:
                        electrical_power = power_value  # Already in kW
                        _LOGGER.debug(
                            "Power value %.2f kW (from unit_of_measurement)",
                            power_value,
                        )
                    else:
                        # Fallback: detect based on value range
                        # Residential heat pumps typically consume 1-20 kW
                        if (
                            power_value > 50
                        ):  # Likely in watts (50W+ is unusual for kW in residential)
                            electrical_power = power_value / 1000
                            _LOGGER.debug(
                                "Power value %.2f treated as watts, converted to %.3f kW (fallback detection)",
                                power_value,
                                electrical_power,
                            )
                        else:  # Already in kW (0-50 kW is reasonable range)
                            electrical_power = power_value
                            _LOGGER.debug(
                                "Power value %.2f treated as kW (fallback detection)",
                                power_value,
                            )

                    if electrical_power <= 0:
                        _LOGGER.debug(
                            "Invalid electrical power from entity %s: %.2f kW",
                            power_entity_id,
                            electrical_power,
                        )
                        return None, None
                    _LOGGER.debug(
                        "Using electrical power %.2f kW from entity %s (raw value: %s)",
                        electrical_power,
                        power_entity_id,
                        power_state.state,
                    )
                    return thermal_power, electrical_power
                except ValueError:
                    _LOGGER.warning(
                        "Could not convert power value '%s' from entity %s to float",
                        power_state.state,
                        power_entity_id,
                    )

        # Calculate electrical power if no power entity
        compressor_current = self.coordinator.data.get("compressor_current")
        if compressor_current is None or compressor_current <= 0:
            _LOGGER.debug(
                "Invalid primary compressor current: %s A", compressor_current
            )
            return None, None

        electrical_power = self._calculate_electrical_power(compressor_current)
        if electrical_power <= 0:
            _LOGGER.debug(
                "Invalid calculated electrical power: %.2f kW", electrical_power
            )
            return None, None

        # Add secondary compressor power for S80 models
        if self.coordinator.is_s80_model():
            r134a_current = self.coordinator.data.get("r134a_compressor_current")
            if r134a_current is not None:
                r134a_current = r134a_current / 10
                additional_power = self._calculate_electrical_power(r134a_current)
                if additional_power > 0:
                    electrical_power += additional_power
                    _LOGGER.debug(
                        "Added R134a compressor power %.2f kW (total: %.2f kW)",
                        additional_power,
                        electrical_power,
                    )

        # Validate electrical power (reasonable range for residential heat pump)
        if electrical_power < 0.1 or electrical_power > 20.0:
            _LOGGER.warning(
                "Calculated electrical power out of reasonable range: %.2f kW",
                electrical_power,
            )
            return None, None

        # Validate COP calculation (reasonable range for heat pump)
        cop_ratio = thermal_power / electrical_power
        if cop_ratio < 0.5 or cop_ratio > 8.0:
            _LOGGER.warning(
                "Calculated COP ratio out of reasonable range: %.2f (thermal: %.2f kW, electrical: %.2f kW)",
                cop_ratio,
                thermal_power,
                electrical_power,
            )
            return None, None

        return thermal_power, electrical_power

    def _is_compressor_running(self, is_r134a: bool = False) -> bool:
        """Check if a compressor is running based on its frequency."""
        if self.coordinator.data is None:
            return False
        freq_key = "r134a_compressor_frequency" if is_r134a else "compressor_frequency"
        frequency = self.coordinator.data.get(freq_key)
        return frequency is not None and frequency > 0

    def _get_cop_value(self) -> StateType:
        """Calculate and return COP value."""
        _LOGGER.debug("Starting COP calculation for %s", self.entity_description.key)

        if self.coordinator.data is None:
            return None

        # Check if primary compressor is running
        if not self._is_compressor_running(False):
            _LOGGER.debug("Primary compressor not running, skipping COP calculation")
            return None

        # Check operation state
        operation_state = self.coordinator.data.get("operation_state")
        if operation_state is None:
            _LOGGER.debug("Operation state not available")
            return None

        # Skip if wrong state
        cop_state_map = {
            "cop_heating": 6,  # heat_thermo_on
            "cop_cooling": 3,  # cool_thermo_on
            "cop_dhw": 8,  # dhw_on
            "cop_pool": 10,  # pool_on
        }
        expected_state = cop_state_map.get(self.entity_description.key)
        if operation_state != expected_state:
            _LOGGER.debug(
                "Wrong operation state for %s: expected %s, got %s",
                self.entity_description.key,
                expected_state,
                operation_state,
            )
            return None

        current_time = time()

        # Add new measurement every minute
        if current_time - self._last_measurement >= COP_MEASUREMENTS_INTERVAL:
            thermal_power, electrical_power = self._calculate_cop_values()

            if thermal_power is not None and electrical_power is not None:
                self._energy_accumulator.add_measurement(
                    thermal_power, electrical_power
                )
                _LOGGER.debug(
                    "Added measurement to energy accumulator: %.2f kW / %.2f kW",
                    thermal_power,
                    electrical_power,
                )

            self._last_measurement = current_time

        # Check if there are enough measurements
        if len(self._energy_accumulator.measurements) < COP_MIN_MEASUREMENTS:
            _LOGGER.debug("Not enough measurements for COP calculation")
            return None

        # Calculate COP from accumulated energy
        cop = self._energy_accumulator.get_cop()
        if cop is not None:
            cop = round(cop, 2)
            _LOGGER.debug(
                "Returning COP %.2f from %d measurements",
                cop,
                len(self._energy_accumulator.measurements),
            )
            return cop

        _LOGGER.debug("No measurements available for COP")
        return None

    async def async_update_timing(self) -> None:
        """Update timing values from history."""
        if self.entity_description.key in (
            "compressor_cycle_time",
            "compressor_runtime",
            "compressor_resttime",
            "r134a_cycle_time",
            "r134a_runtime",
            "r134a_resttime",
        ):
            is_running = self._is_compressor_running(
                "r134a" in self.entity_description.key
            )
            self._compressor_history.add_state(is_running)
            self._timing_values = dict(
                zip(
                    ["cycle_time", "run_time", "rest_time"],
                    self._compressor_history.get_average_times(),
                )
            )

    def _calculate_thermal_power(self) -> float | None:
        """Calculate current thermal power output."""
        if self.coordinator.data is None or not self.coordinator.last_update_success:
            return None

        # Get temperatures from entities if configured, otherwise from registers
        water_inlet = self._get_temperature(
            "water_inlet_temp", CONF_WATER_INLET_TEMP_ENTITY
        )
        water_outlet = self._get_temperature(
            "water_outlet_temp", CONF_WATER_OUTLET_TEMP_ENTITY
        )
        water_flow_raw = self.coordinator.data.get("water_flow")
        water_flow = self.coordinator.convert_water_flow(water_flow_raw)

        if None in (water_inlet, water_outlet, water_flow):
            _LOGGER.debug(
                "Missing values for thermal power calculation: inlet=%.1f°C, outlet=%.1f°C, flow=%s m³/h",
                water_inlet if water_inlet is not None else float("nan"),
                water_outlet if water_outlet is not None else float("nan"),
                water_flow if water_flow is not None else "None",
            )
            return None

        # Convert water flow and calculate thermal power
        water_flow_kgs = water_flow * WATER_FLOW_TO_KGS
        delta_t = water_outlet - water_inlet
        thermal_power = abs(
            water_flow_kgs * WATER_SPECIFIC_HEAT * delta_t
        )  # Result is already in kW

        _LOGGER.debug(
            "Thermal power calculation: %.2f kW (%.2f kg/s * %.2f kJ/kg·K * %.1f K) [flow=%.1f m³/h]",
            thermal_power,
            water_flow_kgs,
            WATER_SPECIFIC_HEAT,
            abs(delta_t),
            water_flow,
        )

        return thermal_power

    def _update_thermal_energy(self) -> None:
        """Update thermal energy calculations."""
        current_time = time()
        current_date = datetime.now().date()

        # Reset daily counter at midnight
        if current_date != self._last_reset:
            self._daily_energy = 0.0
            self._last_reset = current_date
            self._daily_start_time = 0  # Reset start time for new day

        if self.coordinator.data is None:
            return

        # Check if compressor is running
        system_status = self.coordinator.data.get("system_status")
        if system_status is None or not bool(system_status & MASK_COMPRESSOR):
            _LOGGER.debug("Compressor not running, skipping thermal energy calculation")
            return

        # Calculate thermal power
        thermal_power = self._calculate_thermal_power()

        if thermal_power is not None:
            # Initialize daily start time if not set
            if self._daily_start_time == 0:
                self._daily_start_time = current_time
                _LOGGER.debug(
                    "Initializing daily start time to %s",
                    datetime.fromtimestamp(self._daily_start_time).isoformat(),
                )

            # Calculate energy since last measurement
            if self._last_thermal_measurement > 0:
                time_diff = (
                    current_time - self._last_thermal_measurement
                ) / 3600  # Convert to hours
                avg_power = (thermal_power + self._last_power) / 2
                energy = avg_power * time_diff

                self._daily_energy += energy
                self._total_energy += energy

                _LOGGER.debug(
                    "Energy update: +%.3f kWh (%.2f kW * %.3f h), Daily: %.2f kWh, Total: %.2f kWh",
                    energy,
                    avg_power,
                    time_diff,
                    self._daily_energy,
                    self._total_energy,
                )

            self._last_power = thermal_power
            self._last_thermal_measurement = current_time

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        # For timing sensors, return stored values
        if self.entity_description.key in (
            "compressor_cycle_time",
            "compressor_runtime",
            "compressor_resttime",
            "r134a_cycle_time",
            "r134a_runtime",
            "r134a_resttime",
        ):
            if self.entity_description.key in (
                "compressor_cycle_time",
                "r134a_cycle_time",
            ):
                return self._timing_values.get("cycle_time")
            elif self.entity_description.key in ("compressor_runtime", "r134a_runtime"):
                return self._timing_values.get("run_time")
            elif self.entity_description.key in (
                "compressor_resttime",
                "r134a_resttime",
            ):
                return self._timing_values.get("rest_time")

        # For COP sensors, use the COP calculation method
        if self.entity_description.key in (
            "cop_heating",
            "cop_cooling",
            "cop_dhw",
            "cop_pool",
        ):
            return self._get_cop_value()

        # For thermal energy sensors
        if self.entity_description.key in (
            "thermal_power",
            "daily_thermal_energy",
            "total_thermal_energy",
        ):
            self._update_thermal_energy()

            if self.entity_description.key == "thermal_power":
                return round(self._last_power, 2) if self._last_power > 0 else 0
            elif self.entity_description.key == "daily_thermal_energy":
                return round(self._daily_energy, 2)
            else:  # total_thermal_energy
                return round(self._total_energy, 2)

        # For other sensors, use the standard value calculation
        value = self.coordinator.data.get(self.entity_description.register_key)
        if value is None:
            return None

        # Use value_fn if provided
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(value, self.coordinator)

        return value

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        if self.entity_description.key == "alarm_code":
            if self.coordinator.data is None:
                return None
            value = self.coordinator.data.get(self.entity_description.register_key)
            if value is not None:
                alarm_code = str(value)
                return {
                    "code": alarm_code,
                    "description": f"alarm_code_{alarm_code}",
                }
        elif self.entity_description.key in (
            "cop_heating",
            "cop_cooling",
            "cop_dhw",
            "cop_pool",
        ):
            if not hasattr(self, "_energy_accumulator"):
                return {"quality": "no_data"}

            measurements = self._energy_accumulator.measurements
            if not measurements:
                return {"quality": "no_data"}

            # Calculate time span of measurements
            time_span = (
                measurements[-1].timestamp - measurements[0].timestamp
            ).total_seconds() / 60  # minutes
            num_measurements = len(measurements)

            if num_measurements < COP_MIN_MEASUREMENTS or time_span < COP_MIN_TIME_SPAN:
                quality = "insufficient_data"
            elif (
                num_measurements < COP_OPTIMAL_MEASUREMENTS
                or time_span < COP_OPTIMAL_TIME_SPAN
            ):
                quality = "preliminary"
            else:
                quality = "optimal"

            return {
                "quality": quality,
                "measurements": num_measurements,
                "time_span_minutes": round(time_span, 1),
            }
        elif self.entity_description.key == "thermal_power":
            if self._last_thermal_measurement == 0:
                return None

            if self.coordinator.data is None:
                return None

            water_inlet = self._get_temperature(
                "water_inlet_temp", CONF_WATER_INLET_TEMP_ENTITY
            )
            water_outlet = self._get_temperature(
                "water_outlet_temp", CONF_WATER_OUTLET_TEMP_ENTITY
            )
            water_flow_raw = self.coordinator.data.get("water_flow")
            water_flow = self.coordinator.convert_water_flow(water_flow_raw)

            if None in (water_inlet, water_outlet, water_flow):
                return None

            return {
                "last_update": datetime.fromtimestamp(
                    self._last_thermal_measurement
                ).isoformat(),
                "delta_t": round(water_outlet - water_inlet, 2),
                "water_flow": round(water_flow, 2),
                "units": {"delta_t": "°C", "water_flow": "m³/h"},
            }
        elif self.entity_description.key == "daily_thermal_energy":
            if self._last_thermal_measurement == 0 or self._daily_start_time == 0:
                return None

            time_span = (
                datetime.now() - datetime.fromtimestamp(self._daily_start_time)
            ).total_seconds() / 3600  # hours

            avg_power = self._daily_energy / time_span if time_span > 0 else 0

            return {
                "last_reset": self._last_reset.isoformat(),
                "start_time": datetime.fromtimestamp(
                    self._daily_start_time
                ).isoformat(),
                "average_power": round(avg_power, 2),
                "time_span_hours": round(time_span, 1),
                "units": {"average_power": "kW", "time_span": "hours"},
            }
        elif self.entity_description.key == "total_thermal_energy":
            if self._last_thermal_measurement == 0:
                return None

            if self.coordinator.data is None:
                return None

            start_date = datetime.fromtimestamp(self._last_thermal_measurement).date()
            time_span = (
                datetime.now() - datetime.combine(start_date, datetime.min.time())
            ).total_seconds() / 3600  # hours

            avg_power = (
                self._total_energy
                * 24
                / (
                    datetime.now() - datetime.combine(start_date, datetime.min.time())
                ).total_seconds()
                * 3600
            )

            return {
                "start_date": start_date.isoformat(),
                "average_power": round(avg_power, 2),
                "time_span_days": round(time_span / 24, 1),
                "units": {"average_power": "kW", "time_span": "days"},
            }

        return None
