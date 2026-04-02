"""Register map for the ATW-MBS-02 gateway (Before Line-up 2016).

Based on PMML0419A Section 5.2 for Gen 1 Yutaki S and S Combi units.
Key differences from Line-up 2016:
- No Auto HVAC mode (only Cool/Heat)
- No eco mode registers
- No DHW boost/high demand
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
from .atw_mbs_02 import (
    convert_from_tenths,
    convert_pressure,
    convert_signed_16bit,
    deserialize_alarm_code,
    deserialize_operation_state,
    deserialize_otc_method_cooling,
    deserialize_otc_method_heating,
    deserialize_system_state,
    serialize_otc_method_cooling,
    serialize_otc_method_heating,
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

# State Maps — reuse from atw_mbs_02 via imported deserializers

# HVAC Unit mode values (Before Line-up 2016 — NO Auto mode)
HVAC_UNIT_MODE_COOL = 0
HVAC_UNIT_MODE_HEAT = 1


# Conversion functions specific to before-2016


def deserialize_unit_model_pre2016(value: int | None) -> str:
    """Convert a raw unit model ID to a model key (before-2016).

    Mapping from ATW-MBS-02 documentation Section 5.2 (register 1217):
        0: YUTAKI S
        1: YUTAKI S COMBI

    Gen 1 units only support these two models.
    """
    if value is None:
        return "unknown"
    model_map = {
        0: "yutaki_s",
        1: "yutaki_s_combi",
    }
    return model_map.get(value, "unknown")


# Registers grouped by logical device

REGISTER_GATEWAY = {
    "alarm_code": RegisterDefinition(1223, deserializer=deserialize_alarm_code),
    "unit_model": RegisterDefinition(1217, deserializer=deserialize_unit_model_pre2016),
    "central_control_mode": RegisterDefinition(1073),
    "system_config": RegisterDefinition(1074),
    "system_status": RegisterDefinition(1222),
    "system_state": RegisterDefinition(1083, deserializer=deserialize_system_state),
}

REGISTER_CONTROL_UNIT = {
    "unit_power": RegisterDefinition(1000),
    "unit_mode": RegisterDefinition(1001),
    "operation_state": RegisterDefinition(
        1077, deserializer=deserialize_operation_state
    ),
    "operation_state_code": RegisterDefinition(1077),
    "outdoor_temp": RegisterDefinition(1078, deserializer=convert_signed_16bit),
    "water_inlet_temp": RegisterDefinition(1079, deserializer=convert_signed_16bit),
    "water_outlet_temp": RegisterDefinition(
        1199,
        deserializer=convert_signed_16bit,
        fallback=RegisterDefinition(1080, deserializer=convert_signed_16bit),
    ),
    "water_outlet_2_temp": RegisterDefinition(
        1203, deserializer=convert_signed_16bit, sentinel_values=frozenset({-127})
    ),
    "water_outlet_3_temp": RegisterDefinition(
        1204, deserializer=convert_signed_16bit, sentinel_values=frozenset({-127})
    ),
    "water_target_temp": RegisterDefinition(1218, deserializer=convert_signed_16bit),
    "water_flow": RegisterDefinition(1220, deserializer=convert_from_tenths),
    "pump_speed": RegisterDefinition(1221),
    "power_consumption": RegisterDefinition(1098),
}

REGISTER_PRIMARY_COMPRESSOR = {
    "compressor_tg_gas_temp": RegisterDefinition(
        1205, deserializer=convert_signed_16bit
    ),
    "compressor_ti_liquid_temp": RegisterDefinition(
        1206, deserializer=convert_signed_16bit
    ),
    "compressor_td_discharge_temp": RegisterDefinition(
        1207, deserializer=convert_signed_16bit
    ),
    "compressor_te_evaporator_temp": RegisterDefinition(
        1208, deserializer=convert_signed_16bit
    ),
    "compressor_evi_indoor_expansion_valve_opening": RegisterDefinition(1209),
    "compressor_evo_outdoor_expansion_valve_opening": RegisterDefinition(1210),
    "compressor_frequency": RegisterDefinition(1211),
    "compressor_current": RegisterDefinition(1213),
}

# S80 wasn't in Gen 1, but keep for completeness (same addresses as 2016)
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
}

REGISTER_CIRCUIT_1 = {
    "circuit1_power": RegisterDefinition(1002),
    "circuit1_otc_calculation_method_heating": RegisterDefinition(
        1003, deserializer=deserialize_otc_method_heating
    ),
    "circuit1_otc_calculation_method_cooling": RegisterDefinition(
        1004, deserializer=deserialize_otc_method_cooling
    ),
    "circuit1_target_temp": RegisterDefinition(1005, deserializer=convert_from_tenths),
    "circuit1_current_temp": RegisterDefinition(1006, deserializer=convert_from_tenths),
    "circuit1_max_flow_temp_heating_otc": RegisterDefinition(1007),
    "circuit1_max_flow_temp_cooling_otc": RegisterDefinition(1008),
    "circuit1_thermostat": RegisterDefinition(1029),
}

REGISTER_CIRCUIT_2 = {
    "circuit2_power": RegisterDefinition(1009),
    "circuit2_otc_calculation_method_heating": RegisterDefinition(
        1010, deserializer=deserialize_otc_method_heating
    ),
    "circuit2_otc_calculation_method_cooling": RegisterDefinition(
        1011, deserializer=deserialize_otc_method_cooling
    ),
    "circuit2_target_temp": RegisterDefinition(1012, deserializer=convert_from_tenths),
    "circuit2_current_temp": RegisterDefinition(1013, deserializer=convert_from_tenths),
    "circuit2_max_flow_temp_heating_otc": RegisterDefinition(1014),
    "circuit2_max_flow_temp_cooling_otc": RegisterDefinition(1015),
    "circuit2_thermostat": RegisterDefinition(1029),
}

REGISTER_DHW = {
    "dhw_power": RegisterDefinition(1016),
    "dhw_target_temp": RegisterDefinition(1017),
    "dhw_antilegionella": RegisterDefinition(1020),
    "dhw_antilegionella_temp": RegisterDefinition(1021),
    "dhw_current_temp": RegisterDefinition(
        1075, deserializer=convert_signed_16bit, sentinel_values=frozenset({-67})
    ),
    "dhw_antilegionella_status": RegisterDefinition(1069),
    "dhw_antilegionella_temp_status": RegisterDefinition(1070),
}

REGISTER_POOL = {
    "pool_power": RegisterDefinition(1018),
    "pool_target_temp": RegisterDefinition(1019),
    "pool_current_temp": RegisterDefinition(
        1076, deserializer=convert_signed_16bit, sentinel_values=frozenset({-127})
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
# Note: no eco_mode, eco_offset, dhw_boost, dhw_high_demand registers in before-2016
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
    "circuit2_thermostat",
    "circuit2_target_temp",
    "circuit2_current_temp",
    "dhw_power",
    "dhw_target_temp",
    "pool_power",
    "pool_target_temp",
    "dhw_antilegionella",
    "dhw_antilegionella_temp",
}

# In before-2016, system_state (addr 1083) is the H-LINK communication alarm:
#   0: No alarm
#   1: No communication >180s (not the same as 2016 "desync" — non-blocking)
#   2: Data initialization (blocking — gateway not ready)
# Only value 2 is a blocking issue. Value 1 is informational, not a reason
# to skip reads — the gateway may still respond to register queries.
SYSTEM_STATE_ISSUES = {
    2: "initializing_warning",
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

    def serialize_otc_method_heating(self, value: str) -> int:
        """Convert a heating OTC method constant to a raw register value."""
        return serialize_otc_method_heating(value)

    def serialize_otc_method_cooling(self, value: str) -> int:
        """Convert a cooling OTC method constant to a raw register value."""
        return serialize_otc_method_cooling(value)
