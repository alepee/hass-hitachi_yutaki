"""Register map for the ATW-MBS-02 gateway."""

from ....const import (
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
)
from . import HitachiRegisterMap, Keep, RegisterDefinition
from .codecs import (
    ALARM_CODE,
    CENTRAL_CONTROL_MODE,
    OPERATION_STATE,
    OTC_METHOD_COOLING,
    OTC_METHOD_HEATING,
    SIGNED,
    SWITCH,
    SYSTEM_STATE,
    TENTHS,
    UNSIGNED,
    choice,
    unit_model,
)

# System configuration bit masks (from register 1089)
# Bit order per Modbus documentation:
#   Bit 0: Circuit 1 Heating, Bit 1: Circuit 2 Heating
#   Bit 2: Circuit 1 Cooling, Bit 3: Circuit 2 Cooling
MASKS_CIRCUIT = {
    (CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING): 0x0001,
    (CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING): 0x0002,
    (CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING): 0x0004,
    (CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING): 0x0008,
}
MASK_DHW = 0x0010
MASK_POOL = 0x0020
MASK_CIRCUIT1_THERMOSTAT = 0x0040
MASK_CIRCUIT2_THERMOSTAT = 0x0080
MASKS_CIRCUIT_THERMOSTAT = {
    CIRCUIT_PRIMARY_ID: MASK_CIRCUIT1_THERMOSTAT,
    CIRCUIT_SECONDARY_ID: MASK_CIRCUIT2_THERMOSTAT,
}
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


# HVAC Unit mode values (ATW-MBS-02 specific)
HVAC_UNIT_MODE_COOL = 0
HVAC_UNIT_MODE_HEAT = 1
HVAC_UNIT_MODE_AUTO = 2

# Codecs specific to this map
UNIT_MODE = choice(HVAC_UNIT_MODE_COOL, HVAC_UNIT_MODE_HEAT, HVAC_UNIT_MODE_AUTO)
UNIT_MODEL = unit_model(0, 1, 2, 3)  # register 1218: S, S Combi, S80, M

# Registers grouped by logical device

REGISTER_GATEWAY = {
    "alarm_code": RegisterDefinition(1223, ALARM_CODE),
    "unit_model": RegisterDefinition(1218, UNIT_MODEL),
    "central_control_mode": RegisterDefinition(1088, CENTRAL_CONTROL_MODE),
    # 0xFFFF is not a configuration but a garbage read (every capability bit
    # set); filter it rather than create phantom devices (#404).
    "system_config": RegisterDefinition(1089, UNSIGNED),
    "system_status": RegisterDefinition(1222, UNSIGNED),
    "system_state": RegisterDefinition(1094, SYSTEM_STATE),
}

REGISTER_CONTROL_UNIT = {
    "unit_power": RegisterDefinition(1050, SWITCH, write_address=1000),
    "unit_mode": RegisterDefinition(1051, UNIT_MODE, write_address=1001),
    "operation_state": RegisterDefinition(1090, OPERATION_STATE),
    "operation_state_code": RegisterDefinition(1090, UNSIGNED),
    "outdoor_temp": RegisterDefinition(1091, SIGNED),
    "water_inlet_temp": RegisterDefinition(1092, SIGNED),
    "water_outlet_temp": RegisterDefinition(
        1200,
        UNSIGNED,  # HP-level outlet (reg 1201) — correct for all modes including DHW/pool
        fallback=RegisterDefinition(1093, SIGNED),
    ),
    "water_outlet_2_temp": RegisterDefinition(
        1204, SIGNED, sentinel_values=frozenset({-127})
    ),
    "water_outlet_3_temp": RegisterDefinition(
        1205, SIGNED, sentinel_values=frozenset({-127})
    ),
    "water_target_temp": RegisterDefinition(1219, SIGNED),
    "water_flow": RegisterDefinition(1220, TENTHS),
    "pump_speed": RegisterDefinition(1221, UNSIGNED),
    # Unit board (PCB) and controller (LCD) software numbers, read-only.
    # 0xFFFF is a garbage read, not a version (#404).
    "software_pcb": RegisterDefinition(1095, UNSIGNED),
    "software_lcd": RegisterDefinition(1096, UNSIGNED),
}

REGISTER_PRIMARY_COMPRESSOR = {
    "compressor_tg_gas_temp": RegisterDefinition(1206, SIGNED),
    "compressor_ti_liquid_temp": RegisterDefinition(1207, SIGNED),
    "compressor_td_discharge_temp": RegisterDefinition(1208, SIGNED),
    "compressor_te_evaporator_temp": RegisterDefinition(1209, SIGNED),
    "compressor_evi_indoor_expansion_valve_opening": RegisterDefinition(1210, UNSIGNED),
    "compressor_evo_outdoor_expansion_valve_opening": RegisterDefinition(
        1211, UNSIGNED
    ),
    "compressor_frequency": RegisterDefinition(1212, UNSIGNED),
    "compressor_current": RegisterDefinition(1214, UNSIGNED),
}

REGISTER_SECONDARY_COMPRESSOR = {
    "secondary_compressor_discharge_temp": RegisterDefinition(1224, SIGNED),
    "secondary_compressor_suction_temp": RegisterDefinition(1225, SIGNED),
    "secondary_compressor_discharge_pressure": RegisterDefinition(1226, TENTHS),
    "secondary_compressor_suction_pressure": RegisterDefinition(1227, TENTHS),
    "secondary_compressor_frequency": RegisterDefinition(1228, UNSIGNED),
    "secondary_compressor_valve_opening": RegisterDefinition(1229, UNSIGNED),
    "secondary_compressor_current": RegisterDefinition(1230, TENTHS),
    "secondary_compressor_retry_code": RegisterDefinition(1231, UNSIGNED),
}

# A gateway reboot clears the "Thermostat Available" flag, a controller board
# reboot zeroes the room target and the room value (#511). The target goes
# back to its documented range, the room value is seeded with the target (the
# unit idles until the real one is written), then the flag is raised again.
FLAG_KEEP = Keep(valid_range=(0, 1))
ROOM_TARGET_KEEP = {
    cid: Keep(valid_range=(5.0, 35.0), while_on=f"circuit{cid}_thermostat")
    for cid in (1, 2)
}
ROOM_VALUE_KEEP = {
    cid: Keep(
        while_on=f"circuit{cid}_thermostat", seed_from=f"circuit{cid}_target_temp"
    )
    for cid in (1, 2)
}

REGISTER_CIRCUIT_1 = {
    "circuit1_power": RegisterDefinition(1052, SWITCH, write_address=1002),
    "circuit1_otc_calculation_method_heating": RegisterDefinition(
        1053, OTC_METHOD_HEATING, write_address=1003
    ),
    "circuit1_otc_calculation_method_cooling": RegisterDefinition(
        1054, OTC_METHOD_COOLING, write_address=1004
    ),
    "circuit1_max_flow_temp_heating_otc": RegisterDefinition(
        1055, UNSIGNED, write_address=1005
    ),
    "circuit1_max_flow_temp_cooling_otc": RegisterDefinition(
        1056, UNSIGNED, write_address=1006
    ),
    "circuit1_eco_mode": RegisterDefinition(1057, SWITCH, write_address=1007),
    "circuit1_heat_eco_offset": RegisterDefinition(1058, UNSIGNED, write_address=1008),
    "circuit1_cool_eco_offset": RegisterDefinition(1059, UNSIGNED, write_address=1009),
    # 0xFFFF is a garbage read of the CONTROL register, not "enabled" (#404).
    "circuit1_thermostat": RegisterDefinition(1010, SWITCH, keep=FLAG_KEEP),
    "circuit1_target_temp": RegisterDefinition(
        1060,
        TENTHS,
        write_address=1011,
        keep=ROOM_TARGET_KEEP[1],
    ),
    "circuit1_current_temp": RegisterDefinition(
        1061,
        TENTHS,
        write_address=1012,
        keep=ROOM_VALUE_KEEP[1],
    ),
}

REGISTER_CIRCUIT_2 = {
    "circuit2_power": RegisterDefinition(1064, SWITCH, write_address=1013),
    "circuit2_otc_calculation_method_heating": RegisterDefinition(
        1065, OTC_METHOD_HEATING, write_address=1014
    ),
    "circuit2_otc_calculation_method_cooling": RegisterDefinition(
        1066, OTC_METHOD_COOLING, write_address=1015
    ),
    "circuit2_max_flow_temp_heating_otc": RegisterDefinition(
        1067, UNSIGNED, write_address=1016
    ),
    "circuit2_max_flow_temp_cooling_otc": RegisterDefinition(
        1068, UNSIGNED, write_address=1017
    ),
    "circuit2_eco_mode": RegisterDefinition(1069, SWITCH, write_address=1018),
    "circuit2_heat_eco_offset": RegisterDefinition(1070, UNSIGNED, write_address=1019),
    "circuit2_cool_eco_offset": RegisterDefinition(1071, UNSIGNED, write_address=1020),
    "circuit2_thermostat": RegisterDefinition(1021, SWITCH, keep=FLAG_KEEP),
    "circuit2_target_temp": RegisterDefinition(
        1072,
        TENTHS,
        write_address=1022,
        keep=ROOM_TARGET_KEEP[2],
    ),
    "circuit2_current_temp": RegisterDefinition(
        1073,
        TENTHS,
        write_address=1023,
        keep=ROOM_VALUE_KEEP[2],
    ),
    # "MVP: Mixing valve position" (1216, %), circuit 2 only, read-only.
    "circuit2_mixing_valve_position": RegisterDefinition(1216, UNSIGNED),
}

REGISTER_DHW = {
    "dhw_power": RegisterDefinition(1076, SWITCH, write_address=1024),
    "dhw_target_temp": RegisterDefinition(1077, UNSIGNED, write_address=1025),
    "dhw_boost": RegisterDefinition(1078, SWITCH, write_address=1026),
    "dhw_high_demand": RegisterDefinition(1079, SWITCH, write_address=1027),
    "dhw_antilegionella": RegisterDefinition(1084, SWITCH, write_address=1030),
    "dhw_antilegionella_temp": RegisterDefinition(1085, UNSIGNED, write_address=1031),
    "dhw_demand_mode": RegisterDefinition(1079, SWITCH),
    "dhw_current_temp": RegisterDefinition(
        1080, SIGNED, sentinel_values=frozenset({-67})
    ),
    "dhw_antilegionella_status": RegisterDefinition(1084, SWITCH),
    "dhw_antilegionella_temp_status": RegisterDefinition(1085, UNSIGNED),
}

REGISTER_POOL = {
    "pool_power": RegisterDefinition(1081, SWITCH, write_address=1028),
    "pool_target_temp": RegisterDefinition(1082, UNSIGNED, write_address=1029),
    "pool_current_temp": RegisterDefinition(
        1083, SIGNED, sentinel_values=frozenset({-127})
    ),
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
    "circuit1_current_temp",
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
    "circuit2_current_temp",
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
    # 0xFFFF: the gateway answers Modbus but returns no heat pump data at all
    # (every register reads 0xFFFF, field telemetry): treat it as not ready
    # rather than as a healthy state (#404).
    0xFFFF: "no_data_warning",
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

    @property
    def all_registers(self) -> dict[str, RegisterDefinition]:
        """Return all registers in a single map."""
        return ALL_REGISTERS

    @property
    def writable_keys(self) -> set[str]:
        """Return the set of writable register keys."""
        return WRITABLE_KEYS

    @property
    def system_state_issues(self) -> dict[int, str]:
        """Return mapping of system state values to issue keys."""
        return SYSTEM_STATE_ISSUES

    @property
    def masks_circuit(self) -> dict:
        """Return circuit configuration bit masks."""
        return MASKS_CIRCUIT

    @property
    def masks_circuit_thermostat(self) -> dict[int, int]:
        """Return per-circuit "room thermostat available" bit masks."""
        return MASKS_CIRCUIT_THERMOSTAT

    @property
    def mask_dhw(self) -> int:
        """Return DHW configuration bit mask."""
        return MASK_DHW

    @property
    def mask_pool(self) -> int:
        """Return pool configuration bit mask."""
        return MASK_POOL

    @property
    def mask_defrost(self) -> int:
        """Return defrost status bit mask."""
        return MASK_DEFROST

    @property
    def mask_solar(self) -> int:
        """Return solar status bit mask."""
        return MASK_SOLAR

    @property
    def mask_pump1(self) -> int:
        """Return pump 1 status bit mask."""
        return MASK_PUMP1

    @property
    def mask_pump2(self) -> int:
        """Return pump 2 status bit mask."""
        return MASK_PUMP2

    @property
    def mask_pump3(self) -> int:
        """Return pump 3 status bit mask."""
        return MASK_PUMP3

    @property
    def mask_compressor(self) -> int:
        """Return compressor status bit mask."""
        return MASK_COMPRESSOR

    @property
    def mask_boiler(self) -> int:
        """Return boiler status bit mask."""
        return MASK_BOILER

    @property
    def mask_dhw_heater(self) -> int:
        """Return DHW heater status bit mask."""
        return MASK_DHW_HEATER

    @property
    def mask_space_heater(self) -> int:
        """Return space heater status bit mask."""
        return MASK_SPACE_HEATER

    @property
    def mask_smart_function(self) -> int:
        """Return smart function status bit mask."""
        return MASK_SMART_FUNCTION

    @property
    def hvac_unit_mode_cool(self) -> int:
        """Return the raw value for cooling mode."""
        return HVAC_UNIT_MODE_COOL

    @property
    def hvac_unit_mode_heat(self) -> int:
        """Return the raw value for heating mode."""
        return HVAC_UNIT_MODE_HEAT

    @property
    def hvac_unit_mode_auto(self) -> int | None:
        """Return the raw value for auto mode."""
        return HVAC_UNIT_MODE_AUTO
