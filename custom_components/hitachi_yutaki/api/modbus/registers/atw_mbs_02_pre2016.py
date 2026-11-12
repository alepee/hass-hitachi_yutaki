"""Register map for the ATW-MBS-02 gateway (Before Line-up 2016).

Based on PMML0419A Section 5.2 for Gen 1 Yutaki S and S Combi units.
Key differences from Line-up 2016:
- No Auto HVAC mode (only Cool/Heat)
- ECO mode is global (single Space mode toggle + single offset shared by all
  circuits), not per-circuit
- No DHW boost register ("DHW Mode" at addr 1028 exists but is unmapped)
- Different register addresses for most registers
- System config is 8-bit only (no wireless bits)
"""

from ....const import (
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
)
from . import HitachiRegisterMap, RegisterDefinition
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

# System configuration bit masks (from register 1074)
# Only 8 bits — no wireless bits (8-11) in before-2016
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

# System status bit masks (from register 1222 — same as 2016)
MASK_DEFROST = 0x0001
MASK_SOLAR = 0x0002
MASK_PUMP1 = 0x0004
MASK_PUMP2 = 0x0008
MASK_PUMP3 = 0x0010
MASK_COMPRESSOR = 0x0020
MASK_BOILER = 0x0040
MASK_DHW_HEATER = 0x0080
MASK_SPACE_HEATER = 0x0100
# Bit 9 is "Tariff input enable" in before-2016 (not "Smart function")
# Exposed via mask_smart_function for compatibility
MASK_TARIFF_INPUT = 0x0200

# HVAC Unit mode values (Before Line-up 2016 — NO Auto mode)
HVAC_UNIT_MODE_COOL = 0
HVAC_UNIT_MODE_HEAT = 1

# Codecs specific to this map
UNIT_MODE = choice(HVAC_UNIT_MODE_COOL, HVAC_UNIT_MODE_HEAT)
UNIT_MODEL = unit_model(0, 1)  # register 1217: Gen 1 is S or S Combi only

# Registers grouped by logical device

REGISTER_GATEWAY = {
    "alarm_code": RegisterDefinition(1223, ALARM_CODE),
    "unit_model": RegisterDefinition(1217, UNIT_MODEL),
    "central_control_mode": RegisterDefinition(1073, CENTRAL_CONTROL_MODE),
    # 0xFFFF is a garbage read, not a configuration (#404).
    "system_config": RegisterDefinition(1074, UNSIGNED),
    "system_status": RegisterDefinition(1222, UNSIGNED),
    "system_state": RegisterDefinition(1083, SYSTEM_STATE),
    # Gateway "Hardware version" (1081) / "Software version" (1082), read-only.
    # 0xFFFF is a garbage read, not a version (#404).
    "gateway_hw_version": RegisterDefinition(1081, UNSIGNED),
    "gateway_sw_version": RegisterDefinition(1082, UNSIGNED),
}

REGISTER_CONTROL_UNIT = {
    "unit_power": RegisterDefinition(1000, SWITCH),
    "unit_mode": RegisterDefinition(1050, UNIT_MODE, write_address=1001),
    "operation_state": RegisterDefinition(1077, OPERATION_STATE),
    "operation_state_code": RegisterDefinition(1077, UNSIGNED),
    "outdoor_temp": RegisterDefinition(1078, SIGNED),
    "water_inlet_temp": RegisterDefinition(1079, SIGNED),
    "water_outlet_temp": RegisterDefinition(
        1199,
        UNSIGNED,
        fallback=RegisterDefinition(1080, SIGNED),
    ),
    "water_outlet_2_temp": RegisterDefinition(
        1203, SIGNED, sentinel_values=frozenset({-127})
    ),
    "water_outlet_3_temp": RegisterDefinition(
        1204, SIGNED, sentinel_values=frozenset({-127})
    ),
    "water_target_temp": RegisterDefinition(1218, SIGNED),
    "water_flow": RegisterDefinition(1220, TENTHS),
    "pump_speed": RegisterDefinition(1221, UNSIGNED),
    # Global eco mode register (addr 1027, same address for read and write).
    # Write 1=ECO / 0=Comfort. Not present in 2016+ map.
    "eco_mode": RegisterDefinition(1027, SWITCH, write_address=1027),
    # Global eco offset register (addr 1090, write_address=1030).
    # Write range 1~10, validated in set_eco_offset(). Not present in 2016+ map.
    "eco_offset": RegisterDefinition(1090, UNSIGNED, write_address=1030),
    # "PCB1 Software number" (1085) and "LCD Software number" (1084), read-only.
    # 0xFFFF is a garbage read, not a version (#404).
    "software_pcb": RegisterDefinition(1085, UNSIGNED),
    "software_lcd": RegisterDefinition(1084, UNSIGNED),
}

REGISTER_PRIMARY_COMPRESSOR = {
    "compressor_tg_gas_temp": RegisterDefinition(1205, SIGNED),
    "compressor_ti_liquid_temp": RegisterDefinition(1206, SIGNED),
    "compressor_td_discharge_temp": RegisterDefinition(1207, SIGNED),
    "compressor_te_evaporator_temp": RegisterDefinition(1208, SIGNED),
    "compressor_evi_indoor_expansion_valve_opening": RegisterDefinition(1209, UNSIGNED),
    "compressor_evo_outdoor_expansion_valve_opening": RegisterDefinition(
        1210, UNSIGNED
    ),
    "compressor_frequency": RegisterDefinition(1211, UNSIGNED),
    "compressor_current": RegisterDefinition(1213, UNSIGNED),
}

# S80 wasn't in Gen 1, but keep for completeness (same addresses as 2016)
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

REGISTER_CIRCUIT_1 = {
    "circuit1_power": RegisterDefinition(1051, SWITCH, write_address=1002),
    "circuit1_otc_calculation_method_heating": RegisterDefinition(
        1052, OTC_METHOD_HEATING, write_address=1003
    ),
    "circuit1_otc_calculation_method_cooling": RegisterDefinition(
        1053, OTC_METHOD_COOLING, write_address=1004
    ),
    "circuit1_target_temp": RegisterDefinition(1054, TENTHS, write_address=1005),
    "circuit1_current_temp": RegisterDefinition(1055, TENTHS, write_address=1006),
    "circuit1_max_flow_temp_heating_otc": RegisterDefinition(
        1056, UNSIGNED, write_address=1007
    ),
    "circuit1_max_flow_temp_cooling_otc": RegisterDefinition(
        1057, UNSIGNED, write_address=1008
    ),
    # Pre-2016 hardware (PMML0419A Section 5.2) has a SINGLE global
    # "Room Thermostat available" enable at address 1029 (doc: 1028 = DHW Mode,
    # 1029 = Room Thermostat available). Unlike the 2016 line-up, which splits
    # the enable into per-circuit registers 1010/1021, pre-2016 exposes only
    # one. (Per-circuit *availability* is still reported read-only via system-
    # config register 1075 bits 6/7.) It is modelled once here on circuit 1
    # (always present); there is no per-circuit thermostat *control* register,
    # hence no circuit2_thermostat on this map. See #318.
    # 0xFFFF is a garbage read, not "enabled" (#404).
    "circuit1_thermostat": RegisterDefinition(1029, SWITCH),
}

REGISTER_CIRCUIT_2 = {
    "circuit2_power": RegisterDefinition(1058, SWITCH, write_address=1009),
    "circuit2_otc_calculation_method_heating": RegisterDefinition(
        1059, OTC_METHOD_HEATING, write_address=1010
    ),
    "circuit2_otc_calculation_method_cooling": RegisterDefinition(
        1060, OTC_METHOD_COOLING, write_address=1011
    ),
    "circuit2_target_temp": RegisterDefinition(1061, TENTHS, write_address=1012),
    "circuit2_current_temp": RegisterDefinition(1062, TENTHS, write_address=1013),
    "circuit2_max_flow_temp_heating_otc": RegisterDefinition(
        1063, UNSIGNED, write_address=1014
    ),
    "circuit2_max_flow_temp_cooling_otc": RegisterDefinition(
        1064, UNSIGNED, write_address=1015
    ),
    # "MVP: Mixing valve position" (1215, %), circuit 2 only, read-only.
    "circuit2_mixing_valve_position": RegisterDefinition(1215, UNSIGNED),
    # No circuit2_thermostat: pre-2016 has a single global thermostat-available
    # flag (modelled as circuit1_thermostat at address 1029). See #318.
}

REGISTER_DHW = {
    "dhw_power": RegisterDefinition(1065, SWITCH, write_address=1016),
    "dhw_target_temp": RegisterDefinition(1066, UNSIGNED, write_address=1017),
    "dhw_antilegionella": RegisterDefinition(1069, SWITCH, write_address=1020),
    "dhw_antilegionella_temp": RegisterDefinition(1070, UNSIGNED, write_address=1021),
    "dhw_current_temp": RegisterDefinition(
        1075, SIGNED, sentinel_values=frozenset({-67})
    ),
    "dhw_antilegionella_status": RegisterDefinition(1069, SWITCH),
    "dhw_antilegionella_temp_status": RegisterDefinition(1070, UNSIGNED),
}

REGISTER_POOL = {
    "pool_power": RegisterDefinition(1067, SWITCH, write_address=1018),
    "pool_target_temp": RegisterDefinition(1068, UNSIGNED, write_address=1019),
    "pool_current_temp": RegisterDefinition(
        1076, SIGNED, sentinel_values=frozenset({-127})
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

# Writable keys for Before Line-up 2016
# dhw_boost has no before-2016 register; "DHW Mode" (addr 1028, Standard/High
# demand) exists in the doc but is not mapped yet, so dhw_high_demand stays out.
WRITABLE_KEYS = {
    "unit_power",
    "unit_mode",
    "circuit1_power",
    "circuit1_otc_calculation_method_heating",
    "circuit1_otc_calculation_method_cooling",
    "circuit1_max_flow_temp_heating_otc",
    "circuit1_max_flow_temp_cooling_otc",
    "circuit1_thermostat",
    "circuit1_target_temp",
    "circuit1_current_temp",
    "circuit2_power",
    "circuit2_otc_calculation_method_heating",
    "circuit2_otc_calculation_method_cooling",
    "circuit2_max_flow_temp_heating_otc",
    "circuit2_max_flow_temp_cooling_otc",
    "circuit2_target_temp",
    "circuit2_current_temp",
    "dhw_power",
    "dhw_target_temp",
    "pool_power",
    "pool_target_temp",
    "dhw_antilegionella",
    "dhw_antilegionella_temp",
    "eco_mode",
    "eco_offset",
}

# In before-2016, system_state (addr 1083) is the H-LINK communication alarm:
#   0: No alarm
#   1: No communication >180s (not the same as 2016 "desync" — non-blocking)
#   2: Data initialization (blocking — gateway not ready)
# Only value 2 is a blocking issue. Value 1 is informational, not a reason
# to skip reads — the gateway may still respond to register queries.
SYSTEM_STATE_ISSUES = {
    2: "initializing_warning",
    # 0xFFFF: the gateway answers Modbus but returns no heat pump data at all
    # (every register reads 0xFFFF, field telemetry): treat it as not ready
    # rather than as a healthy state (#404).
    0xFFFF: "no_data_warning",
}


class AtwMbs02Pre2016RegisterMap(HitachiRegisterMap):
    """Register map for the ATW-MBS-02 gateway (Before Line-up 2016)."""

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
        """Return smart function status bit mask.

        In before-2016 units, bit 9 is "Tariff input enable" rather than
        "Smart function". Returned here for compatibility with the base class.
        """
        return MASK_TARIFF_INPUT

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
        """Return the raw value for auto mode.

        Before Line-up 2016 units do not support Auto mode.
        """
        return None
