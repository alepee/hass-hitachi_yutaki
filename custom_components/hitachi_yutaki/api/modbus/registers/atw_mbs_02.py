"""Register map for the ATW-MBS-02 gateway."""

from . import HitachiRegisterMap

REGISTER_GATEWAY = {
    "alarm_code": 1223,
    "unit_model": 1218,
    "central_control_mode": 1088,
    "system_config": 1089,
    "system_status": 1222,
    "system_state": 1094,
}

REGISTER_CONTROL_UNIT = {
    "unit_power": 1000,
    "unit_mode": 1001,
    "operation_state": 1090,
    "outdoor_temp": 1091,
    "water_inlet_temp": 1092,
    "water_outlet_temp": 1093,
    "water_target_temp": 1219,
    "water_flow": 1220,
    "pump_speed": 1221,
    "power_consumption": 1098,
}

REGISTER_PRIMARY_COMPRESSOR = {
    "compressor_tg_gas_temp": 1206,
    "compressor_ti_liquid_temp": 1207,
    "compressor_td_discharge_temp": 1208,
    "compressor_te_evaporator_temp": 1209,
    "compressor_evi_indoor_expansion_valve_opening": 1210,
    "compressor_evo_outdoor_expansion_valve_opening": 1211,
    "compressor_frequency": 1212,
    "compressor_current": 1214,
}

REGISTER_SECONDARY_COMPRESSOR = {
    "secondary_compressor_discharge_temp": 1224,
    "secondary_compressor_suction_temp": 1225,
    "secondary_compressor_discharge_pressure": 1226,
    "secondary_compressor_suction_pressure": 1227,
    "secondary_compressor_frequency": 1228,
    "secondary_compressor_valve_opening": 1229,
    "secondary_compressor_current": 1230,
    "secondary_compressor_retry_code": 1231,
    "secondary_compressor_hp_pressure": 1150,
    "secondary_compressor_lp_pressure": 1151,
}

REGISTER_CIRCUIT_1 = {
    "circuit1_power": 1002,
    "circuit1_otc_calculation_method_heating": 1003,
    "circuit1_otc_calculation_method_cooling": 1004,
    "circuit1_max_flow_temp_heating_otc": 1005,
    "circuit1_max_flow_temp_cooling_otc": 1006,
    "circuit1_eco_mode": 1007,
    "circuit1_heat_eco_offset": 1008,
    "circuit1_cool_eco_offset": 1009,
    "circuit1_thermostat": 1010,
    "circuit1_target_temp": 1011,
    "circuit1_current_temp": 1012,
}

REGISTER_CIRCUIT_2 = {
    "circuit2_power": 1013,
    "circuit2_otc_calculation_method_heating": 1014,
    "circuit2_otc_calculation_method_cooling": 1015,
    "circuit2_max_flow_temp_heating_otc": 1016,
    "circuit2_max_flow_temp_cooling_otc": 1017,
    "circuit2_eco_mode": 1018,
    "circuit2_heat_eco_offset": 1019,
    "circuit2_cool_eco_offset": 1020,
    "circuit2_thermostat": 1021,
    "circuit2_target_temp": 1022,
    "circuit2_current_temp": 1023,
}

REGISTER_DHW = {
    "dhw_power": 1024,
    "dhw_target_temp": 1025,
    "dhw_boost": 1026,
    "dhw_high_demand": 1027,
    "dhw_antilegionella": 1030,
    "dhw_antilegionella_temp": 1031,
    "dhw_current_temp": 1080,
    "dhw_antilegionella_status": 1030,
}

REGISTER_POOL = {
    "pool_power": 1028,
    "pool_target_temp": 1029,
    "pool_current_temp": 1083,
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
