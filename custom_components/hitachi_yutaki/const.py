"""Constants for the Hitachi Yutaki integration."""
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_NAME,
    CONF_SLAVE,
    Platform,
)

DOMAIN = "hitachi_yutaki"
DEFAULT_NAME = "Hitachi Yutaki"
DEFAULT_SLAVE = 1
DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 30

# Device types
DEVICE_GATEWAY = "gateway"
DEVICE_CONTROL_UNIT = "control_unit"
DEVICE_CIRCUIT_1 = "circuit_1"
DEVICE_CIRCUIT_2 = "circuit_2"
DEVICE_DHW = "dhw"
DEVICE_POOL = "pool"

# Modbus registers (addresses)
REGISTER_UNIT_MODEL = 1218
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
    "circuit1_water_heating_temp_control": 1003,
    "circuit1_water_cooling_temp_control": 1004,
    "circuit1_water_heating_temp_setting": 1005,
    "circuit1_water_cooling_temp_setting": 1006,
    "circuit1_eco_mode": 1007,
    "circuit1_heat_eco_offset": 1008,
    "circuit1_cool_eco_offset": 1009,
    "circuit1_thermostat": 1010,
    "circuit1_thermostat_temp": 1011,
    "circuit1_room_temp": 1012,
    "circuit2_power": 1013,
    "circuit2_water_heating_temp_control": 1014,
    "circuit2_water_cooling_temp_control": 1015,
    "circuit2_water_heating_temp_setting": 1016,
    "circuit2_water_cooling_temp_setting": 1017,
    "circuit2_eco_mode": 1018,
    "circuit2_heat_eco_offset": 1019,
    "circuit2_cool_eco_offset": 1020,
    "circuit2_thermostat": 1021,
    "circuit2_thermostat_temp": 1022,
    "circuit2_room_temp": 1023,
    "dhw_power": 1024,
    "dhw_temp": 1025,
    "dhw_boost": 1026,
    "dhw_mode": 1027,
    "pool_power": 1028,
    "pool_temp": 1029,
    "antilegionella_power": 1030,
    "antilegionella_temp": 1031,
}

# Sensor registers (addresses)
REGISTER_SENSOR = {
    "outdoor_temp": 1091,
    "water_inlet_temp": 1092,
    "water_outlet_temp": 1093,
    "water_flow": 1220,
    "pump_speed": 1221,
    "dhw_temp": 1080,
    "pool_temp": 1083,
    "compressor_current": 1214,
    "compressor_frequency": 1212,
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
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

MODEL_NAMES = {
    UNIT_MODEL_YUTAKI_S: "Yutaki S",
    UNIT_MODEL_YUTAKI_S_COMBI: "Yutaki S Combi",
    UNIT_MODEL_S80: "Yutaki S80",
    UNIT_MODEL_M: "Yutaki M",
}
