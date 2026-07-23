"""Compressor sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.hitachi_yutaki.const import (
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_TYPES,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfFrequency,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.helpers.entity import EntityCategory

from ...domain.services.refrigerant import (
    STATUS_ALERT,
    STATUS_LEARNING,
    STATUS_OK,
    STATUS_WATCH,
)
from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_compressor_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    compressor_id: int,
    device_type: DEVICE_TYPES,
) -> list[HitachiYutakiSensor]:
    """Build compressor sensor entities."""
    descriptions = _build_compressor_sensor_descriptions(compressor_id)
    return _create_sensors(coordinator, entry_id, descriptions, device_type)


def _build_compressor_sensor_descriptions(
    compressor_id: int,
) -> tuple[HitachiYutakiSensorEntityDescription, ...]:
    """Build compressor sensor descriptions."""
    if compressor_id == 1:
        # Primary compressor sensors
        return (
            HitachiYutakiSensorEntityDescription(
                key="compressor_frequency",
                translation_key="compressor_frequency",
                description="Current operating frequency of the compressor",
                icon="mdi:sine-wave",
                device_class=None,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfFrequency.HERTZ,
                value_fn=lambda coordinator: coordinator.data.get(
                    "compressor_frequency"
                ),
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            HitachiYutakiSensorEntityDescription(
                key="compressor_current",
                translation_key="compressor_current",
                description="Current electrical consumption of the compressor",
                device_class=SensorDeviceClass.CURRENT,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                value_fn=lambda coordinator: coordinator.data.get("compressor_current"),
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            HitachiYutakiSensorEntityDescription(
                key="compressor_tg_gas_temp",
                translation_key="compressor_tg_gas_temp",
                description="Gas temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                value_fn=lambda coordinator: coordinator.data.get(
                    "compressor_tg_gas_temp"
                ),
                entity_category=EntityCategory.DIAGNOSTIC,
                condition=lambda c: c.profile.supports_extended_compressor_sensors,
            ),
            HitachiYutakiSensorEntityDescription(
                key="compressor_ti_liquid_temp",
                translation_key="compressor_ti_liquid_temp",
                description="Liquid temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                value_fn=lambda coordinator: coordinator.data.get(
                    "compressor_ti_liquid_temp"
                ),
                entity_category=EntityCategory.DIAGNOSTIC,
                condition=lambda c: c.profile.supports_extended_compressor_sensors,
            ),
            HitachiYutakiSensorEntityDescription(
                key="compressor_td_discharge_temp",
                translation_key="compressor_td_discharge_temp",
                description="Discharge temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                value_fn=lambda coordinator: coordinator.data.get(
                    "compressor_td_discharge_temp"
                ),
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            HitachiYutakiSensorEntityDescription(
                key="compressor_te_evaporator_temp",
                translation_key="compressor_te_evaporator_temp",
                description="Evaporator temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                value_fn=lambda coordinator: coordinator.data.get(
                    "compressor_te_evaporator_temp"
                ),
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            HitachiYutakiSensorEntityDescription(
                key="compressor_evi_indoor_expansion_valve_opening",
                translation_key="compressor_evi_indoor_expansion_valve_opening",
                description="Indoor expansion valve opening",
                device_class=None,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=PERCENTAGE,
                value_fn=lambda coordinator: coordinator.data.get(
                    "compressor_evi_indoor_expansion_valve_opening"
                ),
                entity_category=EntityCategory.DIAGNOSTIC,
                condition=lambda c: c.profile.supports_extended_compressor_sensors,
            ),
            HitachiYutakiSensorEntityDescription(
                key="compressor_evo_outdoor_expansion_valve_opening",
                translation_key="compressor_evo_outdoor_expansion_valve_opening",
                description="Outdoor expansion valve opening",
                device_class=None,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=PERCENTAGE,
                value_fn=lambda coordinator: coordinator.data.get(
                    "compressor_evo_outdoor_expansion_valve_opening"
                ),
                entity_category=EntityCategory.DIAGNOSTIC,
                condition=lambda c: c.profile.supports_extended_compressor_sensors,
            ),
            HitachiYutakiSensorEntityDescription(
                key="compressor_cycle_time",
                translation_key="compressor_cycle_time",
                description="Average time between compressor starts",
                device_class=SensorDeviceClass.DURATION,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="min",
                entity_category=EntityCategory.DIAGNOSTIC,
                icon="mdi:timer-outline",
                value_fn=lambda c: c.data.get("compressor_cycle_time"),
            ),
            HitachiYutakiSensorEntityDescription(
                key="compressor_runtime",
                translation_key="compressor_runtime",
                description="Average compressor runtime per cycle",
                device_class=SensorDeviceClass.DURATION,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="min",
                entity_category=EntityCategory.DIAGNOSTIC,
                icon="mdi:timer-play-outline",
                value_fn=lambda c: c.data.get("compressor_runtime"),
            ),
            HitachiYutakiSensorEntityDescription(
                key="compressor_resttime",
                translation_key="compressor_resttime",
                description="Average compressor rest time between cycles",
                device_class=SensorDeviceClass.DURATION,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="min",
                entity_category=EntityCategory.DIAGNOSTIC,
                icon="mdi:timer-stop-outline",
                value_fn=lambda c: c.data.get("compressor_resttime"),
            ),
        )
    else:
        # Secondary compressor sensors
        return (
            HitachiYutakiSensorEntityDescription(
                key="secondary_compressor_discharge_temp",
                translation_key="secondary_compressor_discharge_temp",
                description="Temperature of the secondary compressor refrigerant at discharge",
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                value_fn=lambda coordinator: coordinator.data.get(
                    "secondary_compressor_discharge_temp"
                ),
                condition=lambda c: c.profile.supports_secondary_compressor,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            HitachiYutakiSensorEntityDescription(
                key="secondary_compressor_suction_temp",
                translation_key="secondary_compressor_suction_temp",
                description="Temperature of the secondary compressor refrigerant at suction",
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                value_fn=lambda coordinator: coordinator.data.get(
                    "secondary_compressor_suction_temp"
                ),
                condition=lambda c: c.profile.supports_secondary_compressor,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            HitachiYutakiSensorEntityDescription(
                key="secondary_compressor_discharge_pressure",
                translation_key="secondary_compressor_discharge_pressure",
                description="Pressure of the secondary compressor refrigerant at discharge",
                device_class=SensorDeviceClass.PRESSURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfPressure.BAR,
                value_fn=lambda coordinator: coordinator.data.get(
                    "secondary_compressor_discharge_pressure"
                ),
                condition=lambda c: c.profile.supports_secondary_compressor,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            HitachiYutakiSensorEntityDescription(
                key="secondary_compressor_suction_pressure",
                translation_key="secondary_compressor_suction_pressure",
                description="Pressure of the secondary compressor refrigerant at suction",
                device_class=SensorDeviceClass.PRESSURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfPressure.BAR,
                value_fn=lambda coordinator: coordinator.data.get(
                    "secondary_compressor_suction_pressure"
                ),
                condition=lambda c: c.profile.supports_secondary_compressor,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            HitachiYutakiSensorEntityDescription(
                key="secondary_compressor_frequency",
                translation_key="secondary_compressor_frequency",
                description="Operating frequency of the secondary compressor",
                device_class=None,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfFrequency.HERTZ,
                value_fn=lambda coordinator: coordinator.data.get(
                    "secondary_compressor_frequency"
                ),
                condition=lambda c: c.profile.supports_secondary_compressor,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            HitachiYutakiSensorEntityDescription(
                key="secondary_compressor_current",
                translation_key="secondary_compressor_current",
                description="Electrical current drawn by the secondary compressor",
                device_class=SensorDeviceClass.CURRENT,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                value_fn=lambda coordinator: coordinator.data.get(
                    "secondary_compressor_current"
                ),
                condition=lambda c: c.profile.supports_secondary_compressor,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            HitachiYutakiSensorEntityDescription(
                key="secondary_compressor_cycle_time",
                translation_key="secondary_compressor_cycle_time",
                description="Average time between secondary compressor starts",
                device_class=SensorDeviceClass.DURATION,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="min",
                entity_category=EntityCategory.DIAGNOSTIC,
                icon="mdi:timer-outline",
                condition=lambda c: c.profile.supports_secondary_compressor,
                value_fn=lambda c: c.data.get("secondary_compressor_cycle_time"),
            ),
            HitachiYutakiSensorEntityDescription(
                key="secondary_compressor_runtime",
                translation_key="secondary_compressor_runtime",
                description="Average secondary compressor runtime per cycle",
                device_class=SensorDeviceClass.DURATION,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="min",
                entity_category=EntityCategory.DIAGNOSTIC,
                icon="mdi:timer-play-outline",
                condition=lambda c: c.profile.supports_secondary_compressor,
                value_fn=lambda c: c.data.get("secondary_compressor_runtime"),
            ),
            HitachiYutakiSensorEntityDescription(
                key="secondary_compressor_resttime",
                translation_key="secondary_compressor_resttime",
                description="Average secondary compressor rest time between cycles",
                device_class=SensorDeviceClass.DURATION,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="min",
                entity_category=EntityCategory.DIAGNOSTIC,
                icon="mdi:timer-stop-outline",
                condition=lambda c: c.profile.supports_secondary_compressor,
                value_fn=lambda c: c.data.get("secondary_compressor_resttime"),
            ),
        )


def build_refrigerant_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build the refrigerant-circuit anomaly diagnostic sensor."""
    descriptions = _build_refrigerant_sensor_descriptions()
    return _create_sensors(
        coordinator, entry_id, descriptions, DEVICE_PRIMARY_COMPRESSOR
    )


def _refrigerant_attributes(
    coordinator: HitachiYutakiDataCoordinator,
) -> dict[str, object] | None:
    """Expose the detector's deltas and warm-up progress as attributes."""
    if coordinator.data is None:
        return None
    return {
        "superheat_delta": coordinator.data.get("refrigerant_charge_superheat_delta"),
        "exv_delta": coordinator.data.get("refrigerant_charge_exv_delta"),
        "evaporation_temp_delta": coordinator.data.get(
            "refrigerant_charge_evaporation_temp_delta"
        ),
        "baseline_days": coordinator.data.get("refrigerant_charge_baseline_days"),
        "valid_days": coordinator.data.get("refrigerant_charge_valid_days"),
        "alert_streak": coordinator.data.get("refrigerant_charge_alert_streak"),
        "last_valid_day": coordinator.data.get("refrigerant_charge_last_valid_day"),
        "days_since_valid_data": coordinator.data.get(
            "refrigerant_charge_days_since_valid_data"
        ),
    }


def _build_refrigerant_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build refrigerant-circuit anomaly sensor descriptions."""
    return (
        HitachiYutakiSensorEntityDescription(
            key="refrigerant_charge_status",
            translation_key="refrigerant_charge_status",
            description=(
                "Continuous refrigerant-charge anomaly detection (superheat and "
                "expansion-valve drift). Advisory only — complements the mandatory "
                "leak-tightness inspection."
            ),
            device_class=SensorDeviceClass.ENUM,
            options=[STATUS_LEARNING, STATUS_OK, STATUS_WATCH, STATUS_ALERT],
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:gauge-low",
            condition=lambda c: c.profile.supports_extended_compressor_sensors,
            value_fn=lambda c: c.data.get("refrigerant_charge_status"),
            attributes_fn=_refrigerant_attributes,
        ),
    )
