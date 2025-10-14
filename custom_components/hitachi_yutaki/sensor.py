"""Sensor platform for Hitachi Yutaki integration."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
import logging
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
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
    DEVICE_CONTROL_UNIT,
    DEVICE_DHW,
    DEVICE_GATEWAY,
    DEVICE_POOL,
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_SECONDARY_COMPRESSOR,
    DOMAIN,
)
from .coordinator import HitachiYutakiDataCoordinator
from .services.compressor import CompressorHistory
from .services.cop import (
    COP_MEASUREMENTS_HISTORY_SIZE,
    COP_MEASUREMENTS_INTERVAL,
    COP_MEASUREMENTS_PERIOD,
    EnergyAccumulator,
)
from .services.electrical import ElectricalPowerService
from .services.storage import InMemoryStorage
from .services.thermal import (
    ThermalEnergyAccumulator,
    ThermalPowerInput,
    calculate_thermal_power,
)

_LOGGER = logging.getLogger(__name__)

# This is a placeholder for a future configuration option
COMPRESSOR_HISTORY_SIZE = 100


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


GATEWAY_SENSORS: Final[tuple[HitachiYutakiSensorEntityDescription, ...]] = (
    HitachiYutakiSensorEntityDescription(
        key="system_state",
        translation_key="system_state",
        description="System state",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:state-machine",
        register_key="system_state",
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
    ),
    HitachiYutakiSensorEntityDescription(
        key="water_inlet_temp",
        translation_key="water_inlet_temp",
        description="Water inlet temperature measurement",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="water_inlet_temp",
    ),
    HitachiYutakiSensorEntityDescription(
        key="water_outlet_temp",
        translation_key="water_outlet_temp",
        description="Water outlet temperature measurement",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="water_outlet_temp",
    ),
    HitachiYutakiSensorEntityDescription(
        key="water_target_temp",
        translation_key="water_target_temp",
        description="Target water temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="water_target_temp",
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
        key="alarm",
        translation_key="alarm",
        description="Current alarm",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        register_key="alarm_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-circle-outline",
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
        key="secondary_compressor_discharge_temp",
        translation_key="secondary_compressor_discharge_temp",
        description="Temperature of the secondary compressor refrigerant at discharge",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="secondary_compressor_discharge_temp",
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="secondary_compressor_suction_temp",
        translation_key="secondary_compressor_suction_temp",
        description="Temperature of the secondary compressor refrigerant at suction",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        register_key="secondary_compressor_suction_temp",
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="secondary_compressor_discharge_pressure",
        translation_key="secondary_compressor_discharge_pressure",
        description="Pressure of the secondary compressor refrigerant at discharge",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        register_key="secondary_compressor_discharge_pressure",
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="secondary_compressor_suction_pressure",
        translation_key="secondary_compressor_suction_pressure",
        description="Pressure of the secondary compressor refrigerant at suction",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        register_key="secondary_compressor_suction_pressure",
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="secondary_compressor_frequency",
        translation_key="secondary_compressor_frequency",
        description="Operating frequency of the secondary compressor",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        register_key="secondary_compressor_frequency",
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="secondary_compressor_current",
        translation_key="secondary_compressor_current",
        description="Electrical current drawn by the secondary compressor",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        register_key="secondary_compressor_current",
        condition=lambda c: c.is_s80_model(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HitachiYutakiSensorEntityDescription(
        key="secondary_compressor_cycle_time",
        translation_key="secondary_compressor_cycle_time",
        description="Average time between secondary compressor starts",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="min",
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-outline",
        condition=lambda c: c.is_s80_model(),
    ),
    HitachiYutakiSensorEntityDescription(
        key="secondary_compressor_runtime",
        translation_key="secondary_compressor_runtime",
        description="Average secondary compressor runtime per cycle",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="min",
        register_key="system_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-play-outline",
        condition=lambda c: c.is_s80_model(),
    ),
    HitachiYutakiSensorEntityDescription(
        key="secondary_compressor_resttime",
        translation_key="secondary_compressor_resttime",
        description="Average secondary compressor rest time between cycles",
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
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

        # Initialize services based on entity key
        if description.key.startswith("cop_"):
            storage = InMemoryStorage(max_len=COP_MEASUREMENTS_HISTORY_SIZE)
            self._energy_accumulator = EnergyAccumulator(
                storage=storage, period=COP_MEASUREMENTS_PERIOD
            )
            self._electrical_power_service = ElectricalPowerService(
                hass=coordinator.hass,
                config_entry=coordinator.config_entry,
                power_supply=coordinator.power_supply,
            )
            self._last_measurement = 0

        elif "thermal_energy" in description.key or "thermal_power" in description.key:
            self._thermal_energy_accumulator = ThermalEnergyAccumulator()
            self._last_power = 0.0

        elif "compressor" in description.key and "time" in description.key:
            storage = InMemoryStorage(max_len=COMPRESSOR_HISTORY_SIZE)
            self._compressor_service = CompressorHistory(
                storage=storage, max_history=COMPRESSOR_HISTORY_SIZE
            )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        if last_state := await self.async_get_last_state():
            if self.entity_description.key == "total_thermal_energy":
                with suppress(ValueError):
                    self._thermal_energy_accumulator = ThermalEnergyAccumulator(
                        initial_total=float(last_state.state)
                    )
            elif self.entity_description.key == "daily_thermal_energy":
                last_reset = None
                if last_state.attributes.get("last_reset"):
                    with suppress(ValueError):
                        last_reset = datetime.fromisoformat(
                            last_state.attributes["last_reset"]
                        ).date()
                if last_reset == datetime.now().date():
                    with suppress(ValueError):
                        self._thermal_energy_accumulator = ThermalEnergyAccumulator(
                            initial_daily=float(last_state.state)
                        )

    def _get_temperature(self, entity_key: str, fallback_key: str) -> float | None:
        """Get temperature from a configured entity, falling back to coordinator data."""
        entity_id = self.coordinator.config_entry.data.get(entity_key)
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state and state.state not in (None, "unknown", "unavailable"):
                with suppress(ValueError):
                    return float(state.state)
        return self.coordinator.data.get(fallback_key)

    def _is_compressor_running(self, is_secondary: bool = False) -> bool:
        """Check if a compressor is running based on its frequency."""
        if self.coordinator.data is None:
            return False
        freq_key = (
            "secondary_compressor_frequency" if is_secondary else "compressor_frequency"
        )
        frequency = self.coordinator.data.get(freq_key)
        return frequency is not None and frequency > 0

    async def async_update_timing(self) -> None:
        """Update timing values from history."""
        if hasattr(self, "_compressor_service"):
            is_running = self._is_compressor_running(
                "secondary" in self.entity_description.key
            )
            self._compressor_service.add_state(is_running)

    def _get_cop_value(self) -> StateType:
        """Orchestrate COP calculation using services."""
        if self.coordinator.data is None or not self._is_compressor_running(False):
            return None

        current_time = time()
        if current_time - self._last_measurement >= COP_MEASUREMENTS_INTERVAL:
            self._last_measurement = current_time

            water_inlet = self._get_temperature(
                CONF_WATER_INLET_TEMP_ENTITY, "water_inlet_temp"
            )
            water_outlet = self._get_temperature(
                CONF_WATER_OUTLET_TEMP_ENTITY, "water_outlet_temp"
            )
            water_flow = self.coordinator.data.get("water_flow")

            if None in (water_inlet, water_outlet, water_flow):
                return None

            thermal_power = calculate_thermal_power(
                ThermalPowerInput(water_inlet, water_outlet, water_flow)
            )

            compressor_current = self.coordinator.data.get("compressor_current", 0)
            electrical_power = self._electrical_power_service.calculate(
                compressor_current
            )

            if thermal_power > 0 and electrical_power > 0:
                self._energy_accumulator.add_measurement(
                    thermal_power, electrical_power
                )

        return (
            round(self._energy_accumulator.get_cop(), 2)
            if self._energy_accumulator.get_cop()
            else None
        )

    def _update_thermal_energy(self) -> None:
        """Orchestrate thermal energy calculation."""
        if self.coordinator.data is None or not self._is_compressor_running(False):
            return

        water_inlet = self._get_temperature(
            CONF_WATER_INLET_TEMP_ENTITY, "water_inlet_temp"
        )
        water_outlet = self._get_temperature(
            CONF_WATER_OUTLET_TEMP_ENTITY, "water_outlet_temp"
        )
        water_flow = self.coordinator.data.get("water_flow")

        if None in (water_inlet, water_outlet, water_flow):
            return

        thermal_power = calculate_thermal_power(
            ThermalPowerInput(water_inlet, water_outlet, water_flow)
        )
        self._thermal_energy_accumulator.update(thermal_power)
        self._last_power = thermal_power

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
                return round(self._last_power, 2) if self._last_power > 0 else 0
            elif self.entity_description.key == "daily_thermal_energy":
                return round(self._thermal_energy_accumulator.daily_energy, 2)
            else:  # total_thermal_energy
                return round(self._thermal_energy_accumulator.total_energy, 2)

        if (
            "compressor" in self.entity_description.key
            and "time" in self.entity_description.key
        ):
            avg_cycle, avg_run, avg_rest = self._compressor_service.get_average_times()
            if "cycle_time" in self.entity_description.key:
                return avg_cycle
            elif "runtime" in self.entity_description.key:
                return avg_run
            elif "resttime" in self.entity_description.key:
                return avg_rest

        # For simple sensors, directly return the value from coordinator
        return self.coordinator.data.get(self.entity_description.register_key)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        if self.entity_description.key == "alarm":
            if self.coordinator.data is None:
                return None
            value = self.coordinator.data.get(self.entity_description.register_key)
            if value is not None and value != 0:
                return {"code": value}
            return None
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

            if (
                num_measurements < COP_MEASUREMENTS_HISTORY_SIZE
                or time_span < COP_MEASUREMENTS_INTERVAL
            ):
                quality = "insufficient_data"
            elif (
                num_measurements < COP_MEASUREMENTS_HISTORY_SIZE
                or time_span < COP_MEASUREMENTS_INTERVAL
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
            if self._thermal_energy_accumulator.last_measurement_time == 0:
                return None

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

            return {
                "last_update": datetime.fromtimestamp(
                    self._thermal_energy_accumulator.last_measurement_time
                ).isoformat(),
                "delta_t": round(water_outlet - water_inlet, 2),
                "water_flow": round(water_flow, 2),
                "units": {"delta_t": "°C", "water_flow": "m³/h"},
            }
        elif self.entity_description.key == "daily_thermal_energy":
            if (
                self._thermal_energy_accumulator.last_measurement_time == 0
                or self._thermal_energy_accumulator.daily_start_time == 0
            ):
                return None

            time_span = (
                datetime.now()
                - datetime.fromtimestamp(
                    self._thermal_energy_accumulator.daily_start_time
                )
            ).total_seconds() / 3600  # hours

            avg_power = (
                self._thermal_energy_accumulator.daily_energy / time_span
                if time_span > 0
                else 0
            )

            return {
                "last_reset": self._thermal_energy_accumulator.last_reset_date.isoformat(),
                "start_time": datetime.fromtimestamp(
                    self._thermal_energy_accumulator.daily_start_time
                ).isoformat(),
                "average_power": round(avg_power, 2),
                "time_span_hours": round(time_span, 1),
                "units": {"average_power": "kW", "time_span": "hours"},
            }
        elif self.entity_description.key == "total_thermal_energy":
            if self._thermal_energy_accumulator.last_measurement_time == 0:
                return None

            if self.coordinator.data is None:
                return None

            start_date = datetime.fromtimestamp(
                self._thermal_energy_accumulator.last_measurement_time
            ).date()
            time_span = (
                datetime.now() - datetime.combine(start_date, datetime.min.time())
            ).total_seconds() / 3600  # hours

            avg_power = (
                self._thermal_energy_accumulator.total_energy
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
