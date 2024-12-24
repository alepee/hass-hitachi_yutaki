"""Sensor platform for Hitachi Yutaki."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, median
from time import time
from typing import Any, Final

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
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_POWER_ENTITY,
    CONF_VOLTAGE_ENTITY,
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
    COP_ENERGY_ACCUMULATION_PERIOD,
    COP_HISTORY_SIZE,
    COP_UPDATE_INTERVAL,
    DEVICE_CONTROL_UNIT,
    DEVICE_DHW,
    DEVICE_POOL,
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_SECONDARY_COMPRESSOR,
    DOMAIN,
    MASK_COMPRESSOR,
    OPERATION_STATE_MAP,
    POWER_FACTOR,
    THREE_PHASE_FACTOR,
    VOLTAGE_SINGLE_PHASE,
    VOLTAGE_THREE_PHASE,
    WATER_FLOW_TO_KGS,
    WATER_SPECIFIC_HEAT,
)
from .coordinator import HitachiYutakiDataCoordinator


class EnergyAccumulator:
    """Class to accumulate thermal and electrical energy over time."""

    def __init__(self, period: timedelta) -> None:
        """Initialize the accumulator."""
        self.period = period
        self.thermal_energy = 0.0
        self.electrical_energy = 0.0
        self.last_update = datetime.now()
        self.start_time = self.last_update

    def add_measurement(self, thermal_power: float, electrical_power: float) -> None:
        """Add a power measurement and accumulate energy."""
        now = datetime.now()
        dt = (now - self.last_update).total_seconds() / 3600  # Convert to hours

        # Accumulate energy (kWh)
        self.thermal_energy += thermal_power * dt
        self.electrical_energy += electrical_power * dt

        self.last_update = now

        # Reset if period has elapsed
        if now - self.start_time > self.period:
            self.thermal_energy = 0.0
            self.electrical_energy = 0.0
            self.start_time = now

    def get_cop(self) -> float | None:
        """Calculate COP from accumulated energies."""
        if self.electrical_energy <= 0:
            return None
        return self.thermal_energy / self.electrical_energy


@dataclass
class HitachiYutakiSensorEntityDescription(SensorEntityDescription):
    """Class describing Hitachi Yutaki sensor entities."""

    key: str
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    native_unit_of_measurement: str | None = None
    entity_category: EntityCategory | None = None
    icon: str | None = None

    register_key: str | None = None
    needs_conversion: bool = False
    translation_key: str | None = None
    description: str | None = None
    fallback_translation_key: str | None = None
    condition: Callable[[HitachiYutakiDataCoordinator], bool] | None = None


TEMPERATURE_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="outdoor_temp",
        translation_key="outdoor_temp",
        description="Outdoor ambient temperature measurement",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="outdoor_temp",
        needs_conversion=True,
    ),
    HitachiYutakiSensorEntityDescription(
        key="water_inlet_temp",
        translation_key="water_inlet_temp",
        description="Water inlet temperature measurement",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="water_inlet_temp",
        needs_conversion=True,
    ),
    HitachiYutakiSensorEntityDescription(
        key="water_outlet_temp",
        translation_key="water_outlet_temp",
        description="Water outlet temperature measurement",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="water_outlet_temp",
        needs_conversion=True,
    ),
    HitachiYutakiSensorEntityDescription(
        key="water_target_temp",
        translation_key="water_target_temp",
        description="Target water temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="water_target_temp",
        needs_conversion=True,
    ),
)

DHW_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="dhw_current_temp",
        translation_key="dhw_current_temperature",
        description="Current temperature of the domestic hot water",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="dhw_current_temp",
        needs_conversion=True,
    ),
)

POOL_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="pool_current_temp",
        translation_key="pool_current_temperature",
        description="Current temperature of the pool",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="pool_current_temp",
        needs_conversion=True,
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
        needs_conversion=True,
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
        key="operation_state",
        translation_key="operation_state",
        description="Current operation state of the heat pump",
        register_key="operation_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:state-machine",
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
        needs_conversion=True,
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
        needs_conversion=True,
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
        needs_conversion=True,
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
        needs_conversion=True,
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
        needs_conversion=True,
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
        needs_conversion=True,
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="r134a_discharge_pressure",
        translation_key="r134a_discharge_pressure",
        description="Pressure of the R134a refrigerant at compressor discharge",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        register_key="r134a_discharge_pressure",
        needs_conversion=True,
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="r134a_suction_pressure",
        translation_key="r134a_suction_pressure",
        description="Pressure of the R134a refrigerant at compressor suction",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        register_key="r134a_suction_pressure",
        needs_conversion=True,
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
        needs_conversion=True,
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
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
    entities.extend(
        HitachiYutakiSensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
            ),
        )
        for description in CONTROL_UNIT_SENSORS
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

    # Add R134a sensors
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

    async_add_entities(entities)


class HitachiYutakiSensor(
    CoordinatorEntity[HitachiYutakiDataCoordinator], SensorEntity
):
    """Representation of a Hitachi Yutaki Sensor."""

    entity_description: HitachiYutakiSensorEntityDescription

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiSensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.slave}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

        # Initialize variables for cycle time calculation
        if description.key == "compressor_cycle_time":
            self._last_start_time: datetime | None = None
            self._cycle_times: list[float] = []
            self._compressor_running = False

        # Initialize history for COPs
        if description.key in ("cop_heating", "cop_cooling", "cop_dhw", "cop_pool"):
            self._measurements = deque(maxlen=COP_HISTORY_SIZE)
            self._last_measurement = 0
            self._energy_accumulator = EnergyAccumulator(COP_ENERGY_ACCUMULATION_PERIOD)

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
                    pass  # Fall back to calculation if conversion fails

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
                except ValueError:
                    voltage = default_voltage
            else:
                voltage = default_voltage
        else:
            voltage = default_voltage

        if self.coordinator.power_supply == "single":
            # Single phase: P = U * I * cos φ
            return (voltage * current * POWER_FACTOR) / 1000
        else:
            # Three phase: P = U * I * cos φ * √3
            return (voltage * current * POWER_FACTOR * THREE_PHASE_FACTOR) / 1000

    def _calculate_cop_values(self) -> tuple[float | None, float | None]:
        """Calculate thermal and electrical power for COP."""
        if self.coordinator.data is None:
            return None, None

        # Check if compressor is running
        system_status = self.coordinator.data.get("system_status")
        if system_status is None or not bool(system_status & MASK_COMPRESSOR):
            return None, None

        # Get temperatures from entities if configured, otherwise from registers
        water_inlet = self._get_temperature(
            "water_inlet_temp", CONF_WATER_INLET_TEMP_ENTITY
        )
        water_outlet = self._get_temperature(
            "water_outlet_temp", CONF_WATER_OUTLET_TEMP_ENTITY
        )
        water_flow = self.coordinator.data.get("water_flow")

        if None in (water_inlet, water_outlet, water_flow):
            return None, None

        # Convert water flow
        water_flow = water_flow / 10  # Convert to m³/h

        # Calculate thermal power (kW)
        water_flow_kgs = water_flow * WATER_FLOW_TO_KGS
        delta_t = water_outlet - water_inlet
        thermal_power = abs(water_flow_kgs * WATER_SPECIFIC_HEAT * delta_t)

        # Get electrical power
        power_entity_id = self.coordinator.config_entry.data.get(CONF_POWER_ENTITY)
        if power_entity_id:
            power_state = self.hass.states.get(power_entity_id)
            if power_state and power_state.state not in (
                None,
                "unknown",
                "unavailable",
            ):
                try:
                    electrical_power = (
                        float(power_state.state) / 1000
                    )  # Convert W to kW
                    if electrical_power <= 0:
                        return None, None
                    return thermal_power, electrical_power
                except ValueError:
                    pass

        # Calculate electrical power if no power entity
        compressor_current = self.coordinator.data.get("compressor_current")
        if compressor_current is None or compressor_current <= 0:
            return None, None

        electrical_power = self._calculate_electrical_power(compressor_current)
        if electrical_power <= 0:
            return None, None

        # Add secondary compressor power for S80 models
        if self.coordinator.is_s80_model():
            r134a_current = self.coordinator.data.get("r134a_compressor_current")
            if r134a_current is not None:
                r134a_current = r134a_current / 10
                additional_power = self._calculate_electrical_power(r134a_current)
                if additional_power > 0:
                    electrical_power += additional_power

        return thermal_power, electrical_power

    def _get_cop_value(self) -> StateType:
        """Calculate and return COP value."""
        # Check if compressor is running
        system_status = self.coordinator.data.get("system_status")
        if system_status is None or not bool(system_status & MASK_COMPRESSOR):
            return None

        # Check operation state
        operation_state = self.coordinator.data.get("operation_state")
        if operation_state is None:
            return None

        # Skip if wrong state
        state_map = {
            "cop_heating": 6,  # heat_thermo_on
            "cop_cooling": 3,  # cool_thermo_on
            "cop_dhw": 8,  # dhw_on
            "cop_pool": 10,  # pool_on
        }
        if operation_state != state_map.get(self.entity_description.key):
            return None

        current_time = time()

        # Add new measurement every minute
        if current_time - self._last_measurement >= COP_UPDATE_INTERVAL:
            thermal_power, electrical_power = self._calculate_cop_values()

            if thermal_power is not None and electrical_power is not None:
                # If using external temperature sensors, use moving median
                if self.coordinator.config_entry.data.get(
                    CONF_WATER_INLET_TEMP_ENTITY
                ) and self.coordinator.config_entry.data.get(
                    CONF_WATER_OUTLET_TEMP_ENTITY
                ):
                    if electrical_power > 0 and thermal_power / electrical_power <= 8:
                        self._measurements.append(thermal_power / electrical_power)
                # Otherwise use energy accumulation
                else:
                    self._energy_accumulator.add_measurement(
                        thermal_power, electrical_power
                    )

            self._last_measurement = current_time

        # Return COP based on calculation method
        if self.coordinator.config_entry.data.get(
            CONF_WATER_INLET_TEMP_ENTITY
        ) and self.coordinator.config_entry.data.get(CONF_WATER_OUTLET_TEMP_ENTITY):
            if self._measurements:
                return round(median(self._measurements), 2)
        else:
            cop = self._energy_accumulator.get_cop()
            if cop is not None:
                return round(cop, 2)
        return None

    def _get_cycle_time(self, value: int) -> StateType:
        """Calculate and return compressor cycle time."""
        compressor_running = bool(value & MASK_COMPRESSOR)

        # Detect compressor start
        if compressor_running and not self._compressor_running:
            current_time = datetime.now()
            if self._last_start_time is not None:
                cycle_time = (current_time - self._last_start_time).total_seconds() / 60
                self._cycle_times.append(cycle_time)
                # Keep only the last 10 cycles
                if len(self._cycle_times) > 10:
                    self._cycle_times.pop(0)
            self._last_start_time = current_time

        self._compressor_running = compressor_running

        # Calculate average cycle time
        if self._cycle_times:
            return round(mean(self._cycle_times), 1)
        return None

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if (
            self.coordinator.data is None
            or self.entity_description.register_key is None
        ):
            return None

        value = self.coordinator.data.get(self.entity_description.register_key)
        if value is None:
            return None

        # Specific logic for operation state sensor
        if self.entity_description.key == "operation_state":
            return f"operation_state_{OPERATION_STATE_MAP.get(value, 'unknown')}"

        # Specific logic for compressor cycle time sensor
        if self.entity_description.key == "compressor_cycle_time":
            return self._get_cycle_time(value)

        # Convert value if needed
        if self.entity_description.needs_conversion:
            if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE:
                return self.coordinator.convert_temperature(value)
            elif self.entity_description.device_class == SensorDeviceClass.PRESSURE:
                return self.coordinator.convert_pressure(value)
            elif self.entity_description.key == "water_flow":
                return value / 10  # Convert to m³/h
            elif "r134a_current" in self.entity_description.key:
                return value / 10  # Convert to A

        # Specific logic for COP calculations
        if self.entity_description.key in (
            "cop_heating",
            "cop_cooling",
            "cop_dhw",
            "cop_pool",
        ):
            return self._get_cop_value()

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        if self.entity_description.key == "alarm_code":
            value = self.coordinator.data.get(self.entity_description.register_key)
            if value is not None:
                alarm_code = str(value)
                return {
                    "code": alarm_code,
                    "description": f"alarm_code_{alarm_code}",
                }
        return None
