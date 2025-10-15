"""Register map for the ATW-MBS-02 gateway."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import HitachiRegisterMap

# System configuration bit masks (from register 1089)
MASK_CIRCUIT1_HEATING = 0x0001
MASK_CIRCUIT2_HEATING = 0x0002
MASK_CIRCUIT1_COOLING = 0x0004
MASK_CIRCUIT2_COOLING = 0x0008
MASK_DHW = 0x0010
MASK_POOL = 0x0020
MASK_CIRCUIT1_THERMOSTAT = 0x0040
MASK_CIRCUIT2_THERMOSTAT = 0x0080
MASK_CIRCUIT1_WIRELESS = 0x0100
MASK_CIRCUIT2_WIRELESS = 0x0200
MASK_CIRCUIT1_WIRELESS_TEMP = 0x0400
MASK_CIRCUIT2_WIRELESS_TEMP = 0x0800

# System status bit masks (from register 1222 - ATW-MBS-02 specific)
MASK_DEFROST = 0x0001
MASK_SOLAR = 0x0002
MASK_PUMP1 = 0x0004
MASK_PUMP2 = 0x0008
MASK_PUMP3 = 0x0010
MASK_COMPRESSOR = 0x0020
MASK_BOILER = 0x0040
MASK_DHW_HEATER = 0x0080
MASK_SPACE_HEATER = 0x0100
MASK_SMART_FUNCTION = 0x0200


# State Maps
SYSTEM_STATE_MAP = {
    0: "synchronized",
    1: "desynchronized",
    2: "initializing",
}

OPERATION_STATE_MAP = {
    0: "off",
    1: "cool_demand_off",
    2: "cool_thermo_off",
    3: "cool_thermo_on",
    4: "heat_demand_off",
    5: "heat_thermo_off",
    6: "heat_thermo_on",
    7: "dhw_off",
    8: "dhw_on",
    9: "pool_off",
    10: "pool_on",
    11: "alarm",
}

# HVAC Unit mode values (ATW-MBS-02 specific)
HVAC_UNIT_MODE_COOL = 0
HVAC_UNIT_MODE_HEAT = 1
HVAC_UNIT_MODE_AUTO = 2


# Conversion functions


def deserialize_system_state(value: int | None) -> str:
    """Convert a raw system state value to a string."""
    if value is None:
        return "unknown"
    return SYSTEM_STATE_MAP.get(value, "unknown")


def deserialize_operation_state(value: int | None) -> str:
    """Convert a raw operation state value to a string."""
    if value is None:
        return "unknown"
    return f"operation_state_{OPERATION_STATE_MAP.get(value, 'unknown')}"


def deserialize_alarm_code(value: int | None) -> str:
    """Convert a raw alarm code value to a translation key."""
    if value is None:
        return "unknown"
    return f"alarm_code_{value}"


def convert_signed_16bit(value: int | None) -> int | None:
    """Convert signed 16-bit value using 2's complement for negative values.

    Technical pattern: handles values that can be negative.
    Marked as (*1) in ATW-MBS-02 documentation.
    Range: -80~100 for temperatures, varies for other values.

    Examples:
        - Temperatures: outdoor, water inlet/outlet, DHW current, pool current
        - Other signed measurements

    """
    if value is None:
        return None
    if value == 0xFFFF:  # Special value for sensor error
        return None
    if value > 32767:  # Handle negative values (2's complement)
        value -= 65536
    return int(value)


def convert_from_tenths(value: int | None) -> float | None:
    """Convert values stored in tenths to their actual decimal value.

    Technical pattern: division by 10 to extract decimal precision.
    Marked as (*3) in ATW-MBS-02 documentation for temperatures.

    Examples:
        - Temperatures: 500 → 50.0 °C (setpoints, targets, max flow temps)
        - Water flow: 50 → 5.0 m³/h
        - Secondary compressor current: 50 → 5.0 A

    """
    if value is None:
        return None
    if value == 0xFFFF:  # Special value for sensor error
        return None
    return float(value) / 10.0


def convert_pressure(value: int | None) -> float | None:
    """Convert pressure value to bar.

    Raw values are stored in hundredths of MPa (e.g., 510 = 5.10 MPa).
    Since 1 MPa = 10 bar, dividing by 10 converts to bar.
    Example: 510 (raw) = 5.10 MPa = 51.0 bar

    Per ATW-MBS-02 documentation:
    - Discharge pressure: 0~510 (0.00~5.10 MPa)
    - Suction pressure: 0~255 (0.00~2.55 MPa)
    """
    if value is None:
        return None
    return float(value) / 10.0


@dataclass
class RegisterDefinition:
    """Class to define a register."""

    address: int
    deserializer: Callable[[Any], Any] | None = None
    serializer: Callable[[Any], Any] | None = None


# Registers grouped by logical device

REGISTER_GATEWAY = {
    "alarm_code": RegisterDefinition(1223, deserializer=deserialize_alarm_code),
    "unit_model": RegisterDefinition(1218),
    "central_control_mode": RegisterDefinition(1088),
    "system_config": RegisterDefinition(1089),
    "system_status": RegisterDefinition(1222),
    "system_state": RegisterDefinition(1094, deserializer=deserialize_system_state),
}

REGISTER_CONTROL_UNIT = {
    "unit_power": RegisterDefinition(1000),
    "unit_mode": RegisterDefinition(1001),
    "operation_state": RegisterDefinition(
        1090, deserializer=deserialize_operation_state
    ),
    "outdoor_temp": RegisterDefinition(1091, deserializer=convert_signed_16bit),
    "water_inlet_temp": RegisterDefinition(1092, deserializer=convert_signed_16bit),
    "water_outlet_temp": RegisterDefinition(1093, deserializer=convert_signed_16bit),
    "water_target_temp": RegisterDefinition(1219, deserializer=convert_signed_16bit),
    "water_flow": RegisterDefinition(1220, deserializer=convert_from_tenths),
    "pump_speed": RegisterDefinition(1221),
    "power_consumption": RegisterDefinition(1098),
}

REGISTER_PRIMARY_COMPRESSOR = {
    "compressor_tg_gas_temp": RegisterDefinition(
        1206, deserializer=convert_signed_16bit
    ),
    "compressor_ti_liquid_temp": RegisterDefinition(
        1207, deserializer=convert_signed_16bit
    ),
    "compressor_td_discharge_temp": RegisterDefinition(
        1208, deserializer=convert_signed_16bit
    ),
    "compressor_te_evaporator_temp": RegisterDefinition(
        1209, deserializer=convert_signed_16bit
    ),
    "compressor_evi_indoor_expansion_valve_opening": RegisterDefinition(1210),
    "compressor_evo_outdoor_expansion_valve_opening": RegisterDefinition(1211),
    "compressor_frequency": RegisterDefinition(1212),
    "compressor_current": RegisterDefinition(1214),
}

REGISTER_SECONDARY_COMPRESSOR = {
    "secondary_compressor_discharge_temp": RegisterDefinition(
        1224, deserializer=convert_signed_16bit
    ),
    "secondary_compressor_suction_temp": RegisterDefinition(
        1225, deserializer=convert_signed_16bit
    ),
    "secondary_compressor_discharge_pressure": RegisterDefinition(
        1226, deserializer=convert_pressure
    ),
    "secondary_compressor_suction_pressure": RegisterDefinition(
        1227, deserializer=convert_pressure
    ),
    "secondary_compressor_frequency": RegisterDefinition(1228),
    "secondary_compressor_valve_opening": RegisterDefinition(1229),
    "secondary_compressor_current": RegisterDefinition(
        1230, deserializer=convert_from_tenths
    ),
    "secondary_compressor_retry_code": RegisterDefinition(1231),
    "secondary_compressor_hp_pressure": RegisterDefinition(
        1150, deserializer=convert_pressure
    ),
    "secondary_compressor_lp_pressure": RegisterDefinition(
        1151, deserializer=convert_pressure
    ),
}

REGISTER_CIRCUIT_1 = {
    "circuit1_power": RegisterDefinition(1002),
    "circuit1_otc_calculation_method_heating": RegisterDefinition(1003),
    "circuit1_otc_calculation_method_cooling": RegisterDefinition(1004),
    "circuit1_max_flow_temp_heating_otc": RegisterDefinition(
        1005, deserializer=convert_from_tenths
    ),
    "circuit1_max_flow_temp_cooling_otc": RegisterDefinition(
        1006, deserializer=convert_from_tenths
    ),
    "circuit1_eco_mode": RegisterDefinition(1007),
    "circuit1_heat_eco_offset": RegisterDefinition(1008),
    "circuit1_cool_eco_offset": RegisterDefinition(1009),
    "circuit1_thermostat": RegisterDefinition(1010),
    "circuit1_target_temp": RegisterDefinition(1011, deserializer=convert_from_tenths),
    "circuit1_current_temp": RegisterDefinition(1012, deserializer=convert_from_tenths),
}

REGISTER_CIRCUIT_2 = {
    "circuit2_power": RegisterDefinition(1013),
    "circuit2_otc_calculation_method_heating": RegisterDefinition(1014),
    "circuit2_otc_calculation_method_cooling": RegisterDefinition(1015),
    "circuit2_max_flow_temp_heating_otc": RegisterDefinition(
        1016, deserializer=convert_from_tenths
    ),
    "circuit2_max_flow_temp_cooling_otc": RegisterDefinition(
        1017, deserializer=convert_from_tenths
    ),
    "circuit2_eco_mode": RegisterDefinition(1018),
    "circuit2_heat_eco_offset": RegisterDefinition(1019),
    "circuit2_cool_eco_offset": RegisterDefinition(1020),
    "circuit2_thermostat": RegisterDefinition(1021),
    "circuit2_target_temp": RegisterDefinition(1022, deserializer=convert_from_tenths),
    "circuit2_current_temp": RegisterDefinition(1023, deserializer=convert_from_tenths),
}

REGISTER_DHW = {
    "dhw_power": RegisterDefinition(1024),
    "dhw_target_temp": RegisterDefinition(1025, deserializer=convert_from_tenths),
    "dhw_boost": RegisterDefinition(1026),
    "dhw_high_demand": RegisterDefinition(1027),
    "dhw_antilegionella": RegisterDefinition(1030),
    "dhw_antilegionella_temp": RegisterDefinition(
        1031, deserializer=convert_from_tenths
    ),
    "dhw_current_temp": RegisterDefinition(1080, deserializer=convert_signed_16bit),
    "dhw_antilegionella_status": RegisterDefinition(1030),
}

REGISTER_POOL = {
    "pool_power": RegisterDefinition(1028),
    "pool_target_temp": RegisterDefinition(1029, deserializer=convert_from_tenths),
    "pool_current_temp": RegisterDefinition(1083, deserializer=convert_signed_16bit),
}

# All registers in a single map for easy lookup
ALL_REGISTERS = {
    **REGISTER_GATEWAY,
    **REGISTER_CONTROL_UNIT,
    **REGISTER_PRIMARY_COMPRESSOR,
    **REGISTER_SECONDARY_COMPRESSOR,
    **REGISTER_CIRCUIT_1,
    **REGISTER_CIRCUIT_2,
    **REGISTER_DHW,
    **REGISTER_POOL,
}

# Keys for registers that can be written to
WRITABLE_KEYS = {
    "unit_power",
    "unit_mode",
    "circuit1_power",
    "circuit1_otc_calculation_method_heating",
    "circuit1_otc_calculation_method_cooling",
    "circuit1_max_flow_temp_heating_otc",
    "circuit1_max_flow_temp_cooling_otc",
    "circuit1_eco_mode",
    "circuit1_heat_eco_offset",
    "circuit1_cool_eco_offset",
    "circuit1_thermostat",
    "circuit1_target_temp",
    "circuit2_power",
    "circuit2_otc_calculation_method_heating",
    "circuit2_otc_calculation_method_cooling",
    "circuit2_max_flow_temp_heating_otc",
    "circuit2_max_flow_temp_cooling_otc",
    "circuit2_eco_mode",
    "circuit2_heat_eco_offset",
    "circuit2_cool_eco_offset",
    "circuit2_thermostat",
    "circuit2_target_temp",
    "dhw_power",
    "dhw_target_temp",
    "dhw_boost",
    "dhw_high_demand",
    "pool_power",
    "pool_target_temp",
    "dhw_antilegionella",
    "dhw_antilegionella_temp",
}

SYSTEM_STATE_ISSUES = {
    1: "desync_warning",
    2: "initializing_warning",
}


class AtwMbs02RegisterMap(HitachiRegisterMap):
    """Register map for the ATW-MBS-02 gateway."""

    @property
    def gateway_keys(self) -> list[str]:
        """Return the list of gateway keys."""
        return list(REGISTER_GATEWAY.keys())

    @property
    def control_unit_keys(self) -> list[str]:
        """Return the list of control unit keys."""
        return list(REGISTER_CONTROL_UNIT.keys())

    @property
    def primary_compressor_keys(self) -> list[str]:
        """Return the list of primary compressor keys."""
        return list(REGISTER_PRIMARY_COMPRESSOR.keys())

    @property
    def secondary_compressor_keys(self) -> list[str]:
        """Return the list of secondary compressor keys."""
        return list(REGISTER_SECONDARY_COMPRESSOR.keys())

    @property
    def circuit_1_keys(self) -> list[str]:
        """Return the list of circuit 1 keys."""
        return list(REGISTER_CIRCUIT_1.keys())

    @property
    def circuit_2_keys(self) -> list[str]:
        """Return the list of circuit 2 keys."""
        return list(REGISTER_CIRCUIT_2.keys())

    @property
    def dhw_keys(self) -> list[str]:
        """Return the list of DHW keys."""
        return list(REGISTER_DHW.keys())

    @property
    def pool_keys(self) -> list[str]:
        """Return the list of pool keys."""
        return list(REGISTER_POOL.keys())
