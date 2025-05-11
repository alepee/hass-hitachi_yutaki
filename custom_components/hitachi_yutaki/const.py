"""Constants for the Hitachi Yutaki integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "hitachi_yutaki"
MANUFACTURER = "Hitachi"
GATEWAY_MODEL = "ATW-MBS-02"

VERSION = "1.8.0"

# Default values
DEFAULT_NAME = "Hitachi Yutaki"
DEFAULT_HOST = "192.168.0.4"
DEFAULT_SLAVE = 1
DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_POWER_SUPPLY = "single"

# Device types
DEVICE_GATEWAY = "gateway"
DEVICE_CONTROL_UNIT = "control_unit"
DEVICE_PRIMARY_COMPRESSOR = "outdoor_compressor"
DEVICE_SECONDARY_COMPRESSOR = "indoor_compressor"
DEVICE_CIRCUIT_1 = "circuit_1"
DEVICE_CIRCUIT_2 = "circuit_2"
DEVICE_DHW = "dhw"
DEVICE_POOL = "pool"

# Modbus registers (addresses)
REGISTER_UNIT_MODEL = 1218
REGISTER_CENTRAL_CONTROL_MODE = 1088
REGISTER_SYSTEM_CONFIG = 1089
REGISTER_SYSTEM_STATUS = 1222

# Unit models
UNIT_MODEL_YUTAKI_S = 0
UNIT_MODEL_YUTAKI_S_COMBI = 1
UNIT_MODEL_S80 = 2
UNIT_MODEL_M = 3

# System configuration bit masks
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

# System status bit masks
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

# Control registers (addresses)
REGISTER_CONTROL = {
    "unit_power": 1000,
    "unit_mode": 1001,
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
    "dhw_power": 1024,
    "dhw_target_temp": 1025,
    "dhw_boost": 1026,
    "dhw_high_demand": 1027,
    "pool_power": 1028,
    "pool_target_temp": 1029,
    "dhw_antilegionella": 1030,
    "dhw_antilegionella_temp": 1031,
}

# Sensor registers (addresses)
REGISTER_SENSOR = {
    "operation_state": 1090,
    "outdoor_temp": 1091,
    "water_inlet_temp": 1092,
    "water_outlet_temp": 1093,
    "water_target_temp": 1219,
    "water_flow": 1220,
    "pump_speed": 1221,
    "dhw_current_temp": 1080,
    "pool_current_temp": 1083,
    "compressor_tg_gas_temp": 1206,
    "compressor_ti_liquid_temp": 1207,
    "compressor_td_discharge_temp": 1208,
    "compressor_te_evaporator_temp": 1209,
    "compressor_evi_indoor_expansion_valve_opening": 1210,
    "compressor_evo_outdoor_expansion_valve_opening": 1211,
    "compressor_frequency": 1212,
    "compressor_current": 1214,
    "power_consumption": 1098,
    "alarm_code": 1223,
}

# R134a specific registers (S80 only)
REGISTER_R134A = {
    "r134a_discharge_temp": 1224,
    "r134a_suction_temp": 1225,
    "r134a_discharge_pressure": 1226,
    "r134a_suction_pressure": 1227,
    "r134a_compressor_frequency": 1228,
    "r134a_valve_opening": 1229,
    "r134a_compressor_current": 1230,
    "r134a_retry_code": 1231,
}

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]

MODEL_NAMES = {
    UNIT_MODEL_YUTAKI_S: "Yutaki S",
    UNIT_MODEL_YUTAKI_S_COMBI: "Yutaki S Combi",
    UNIT_MODEL_S80: "Yutaki S80",
    UNIT_MODEL_M: "Yutaki M",
}

# HVAC modes
HVAC_MODE_MAP = {
    "cool": 0,
    "heat": 1,
    "auto": 2,
}

# Central control modes
CENTRAL_CONTROL_MODE_MAP = {
    "local": 0,
    "air": 1,
    "water": 2,
    "total": 3,
}

# HVAC presets
PRESET_COMFORT = "comfort"
PRESET_ECO = "eco"

# DHW presets
PRESET_DHW_OFF = "off"
PRESET_DHW_HEAT_PUMP = "heat_pump"
PRESET_DHW_HIGH_DEMAND = "high_demand"

# Operation state values
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

# Configuration options
CONF_SLAVE = "slave"
CONF_POWER_SUPPLY = "power_supply"
CONF_VOLTAGE_ENTITY = "voltage_entity"
CONF_POWER_ENTITY = "power_entity"
CONF_WATER_INLET_TEMP_ENTITY = "water_inlet_temp_entity"
CONF_WATER_OUTLET_TEMP_ENTITY = "water_outlet_temp_entity"
CONF_DEV_MODE = "dev_mode"

# Electrical constants
VOLTAGE_SINGLE_PHASE = 230  # Volts
VOLTAGE_THREE_PHASE = 400  # Volts
POWER_FACTOR = 0.85  # cos φ
THREE_PHASE_FACTOR = 1.732  # √3

# Water constants
WATER_SPECIFIC_HEAT = 4.18  # kJ/kg·K
WATER_FLOW_TO_KGS = 1000 / 3600  # Conversion from m³/h to kg/s

# COP calculation constants
COP_MEASUREMENTS_INTERVAL = 30  # Seconds between COP measurements
COP_MEASUREMENTS_HISTORY_SIZE = 60  # Number of measurements to keep in history
COP_MEASUREMENTS_PERIOD = timedelta(minutes=30)  # Period for energy accumulation

# COP quality thresholds
COP_MIN_MEASUREMENTS = 6  # Minimum number of measurements for COP calculation
COP_MIN_TIME_SPAN = 3  # Minimum time span in minutes for COP calculation
COP_OPTIMAL_MEASUREMENTS = 10  # Number of measurements for optimal COP calculation
COP_OPTIMAL_TIME_SPAN = 15  # Time span in minutes for optimal COP calculation
