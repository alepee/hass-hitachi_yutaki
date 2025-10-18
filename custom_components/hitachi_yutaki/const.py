"""Constants for the Hitachi Yutaki integration."""

from typing import Final

from packaging import version
import pymodbus

from homeassistant.const import Platform

DOMAIN: Final = "hitachi_yutaki"
MANUFACTURER = "Hitachi"
VERSION = "1.9.3"

# Default values
DEFAULT_NAME = "Hitachi Heat Pump"
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

# Configuration options
CONF_SLAVE = "slave"
CONF_POWER_SUPPLY = "power_supply"
CONF_VOLTAGE_ENTITY = "voltage_entity"
CONF_POWER_ENTITY = "power_entity"
CONF_WATER_INLET_TEMP_ENTITY = "water_inlet_temp_entity"
CONF_WATER_OUTLET_TEMP_ENTITY = "water_outlet_temp_entity"
CONF_DEV_MODE = "dev_mode"

# COP calculation parameters
COP_MEASUREMENTS_INTERVAL = 60  # seconds
COP_MEASUREMENTS_PERIOD = 30  # minutes
COP_MIN_MEASUREMENTS = 5
COP_OPTIMAL_MEASUREMENTS = 15
COP_MIN_TIME_SPAN = 5  # minutes
COP_OPTIMAL_TIME_SPAN = 15  # minutes
COP_MEASUREMENTS_HISTORY_SIZE = 100

# Electrical constants
POWER_FACTOR = 0.9
THREE_PHASE_FACTOR = 1.732
VOLTAGE_SINGLE_PHASE = 230.0
VOLTAGE_THREE_PHASE = 400.0

# Water constants
WATER_FLOW_TO_KGS = 0.277778  # 1 m³/h = 1000 L/h = 1000 kg/h = 0.277778 kg/s
WATER_SPECIFIC_HEAT = 4.185  # kJ/kg·K


def get_pymodbus_device_param():
    """Get the correct parameter name for pymodbus device/slave based on version.

    Returns:
        str: 'device_id' for pymodbus >= 3.10.0, 'slave' for older versions

    """
    try:
        pymodbus_version = version.parse(pymodbus.__version__)
        if pymodbus_version >= version.parse("3.10.0"):
            return "device_id"
        else:
            return "slave"
    except (ImportError, AttributeError):
        # Fallback to 'slave' if pymodbus is not available or version cannot be determined
        return "slave"
