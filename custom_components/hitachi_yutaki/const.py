"""Constants for the Hitachi Yutaki integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "hitachi_yutaki"
MANUFACTURER = "Hitachi"
GATEWAY_MODEL = "ATW-MBS-02"

VERSION = "2.0.0-beta.1"

# Default values
DEFAULT_NAME = "Hitachi Yutaki"
DEFAULT_HOST = "192.168.0.4"
DEFAULT_DEVICE_ID = 1
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
REGISTER_SYSTEM_STATE = 1094

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

# Control registers moved to api/modbus/registers/atw_mbs_02.py
# Legacy constant removed. Use the register map via the API client.

# Sensor registers moved to api/modbus/registers/atw_mbs_02.py
# Legacy constant removed. Use the register map via the API client.

# R134a-specific registers moved to api/modbus/registers/atw_mbs_02.py
# Legacy constant removed. Use the register map via the API client.

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
    Platform.BUTTON,
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

# System state values
SYSTEM_STATE_MAP = {
    0: "synchronized",
    1: "desynchronized",
    2: "initializing",
}

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
CONF_DEVICE_ID = "device_id"
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
