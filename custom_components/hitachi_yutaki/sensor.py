"""Sensor platform for Hitachi Yutaki."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
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
    CONF_VOLTAGE_ENTITY,
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
    UNIT_MODEL_S80,
    VOLTAGE_SINGLE_PHASE,
    VOLTAGE_THREE_PHASE,
    WATER_FLOW_TO_KGS,
    WATER_SPECIFIC_HEAT,
)
from .coordinator import HitachiYutakiDataCoordinator


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
    model_required: str | None = None
    translation_key: str | None = None
    description: str | None = None
    fallback_translation_key: str | None = None


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
        key="cop",
        translation_key="cop",
        description="Coefficient of Performance",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:heat-pump",
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
        model_required=UNIT_MODEL_S80,
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
        model_required=UNIT_MODEL_S80,
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
        model_required=UNIT_MODEL_S80,
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
        model_required=UNIT_MODEL_S80,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="r134a_compressor_frequency",
        translation_key="r134a_compressor_frequency",
        description="Operating frequency of the R134a compressor",
        icon="mdi:sine-wave",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        register_key="r134a_compressor_frequency",
        model_required=UNIT_MODEL_S80,
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
        model_required=UNIT_MODEL_S80,
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

    # Add R134a sensors only if unit is S80 and they are relevant
    if coordinator.is_s80_model():
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

        # Initialiser les variables pour le calcul du temps de cycle
        if description.key == "compressor_cycle_time":
            self._last_start_time: datetime | None = None
            self._cycle_times: list[float] = []
            self._compressor_running = False

        # Initialiser l'historique pour le COP
        if description.key == "cop":
            self._measurements = deque(maxlen=COP_HISTORY_SIZE)
            self._last_measurement = 0

    def _calculate_electrical_power(self, current: float) -> float:
        """Calculate electrical power in kW based on current and power supply type."""
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

        water_inlet = self.coordinator.data.get("water_inlet_temp")
        water_outlet = self.coordinator.data.get("water_outlet_temp")
        water_flow = self.coordinator.data.get("water_flow")
        compressor_current = self.coordinator.data.get("compressor_current")

        if None in (water_inlet, water_outlet, water_flow, compressor_current):
            return None, None

        # Convert temperatures
        water_inlet = self.coordinator.convert_temperature(water_inlet)
        water_outlet = self.coordinator.convert_temperature(water_outlet)
        water_flow = water_flow / 10  # Convert to m³/h

        # Calculate thermal power (kW)
        water_flow_kgs = water_flow * WATER_FLOW_TO_KGS
        delta_t = water_outlet - water_inlet
        thermal_power = water_flow_kgs * WATER_SPECIFIC_HEAT * delta_t

        # Calculate electrical power (kW)
        electrical_power = self._calculate_electrical_power(compressor_current)

        # Add secondary compressor power for S80 models
        if self.coordinator.is_s80_model():
            r134a_current = self.coordinator.data.get("r134a_compressor_current")
            if r134a_current is not None:
                r134a_current = r134a_current / 10
                electrical_power += self._calculate_electrical_power(r134a_current)

        return thermal_power, electrical_power

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
            compressor_running = bool(value & MASK_COMPRESSOR)

            # Detect compressor start
            if compressor_running and not self._compressor_running:
                current_time = datetime.now()
                if self._last_start_time is not None:
                    cycle_time = (
                        current_time - self._last_start_time
                    ).total_seconds() / 60
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

        # Specific logic for COP calculation
        if self.entity_description.key == "cop":
            # Check if compressor is running
            system_status = self.coordinator.data.get("system_status")
            if system_status is None or not bool(system_status & MASK_COMPRESSOR):
                return None

            current_time = time()

            # Add new measurement every minute
            if current_time - self._last_measurement >= COP_UPDATE_INTERVAL:
                thermal_power, electrical_power = self._calculate_cop_values()
                if (
                    thermal_power is not None
                    and electrical_power is not None
                    and electrical_power > 0
                ):
                    self._measurements.append(thermal_power / electrical_power)
                self._last_measurement = current_time

            # Calculate median COP if we have measurements
            if self._measurements:
                return round(median(self._measurements), 2)
            return None

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
