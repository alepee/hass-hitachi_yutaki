"""Register map for the HC-A(16/64)MB gateway.

The HC-A(8/16/64)MB is a newer Hitachi Network/Modbus gateway for ATW heat pumps.
It uses a different addressing scheme from the ATW-MBS-02:
  - Base address: 5000 + (unit_id * 200)
  - CONTROL registers (R/W): offsets 50-86
  - STATUS registers (R): offsets 100-192

References:
  - HC-A(16/64)MB Modbus documentation (section 5.2: Indoor Unit Register Block)
  - Nathan-38 hardware validation (issue #96, Yutaki S2 6kW)

"""

from ....const import (
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    OTCCalculationMethod,
)
from . import HitachiRegisterMap, RegisterDefinition

# ──────────────────────────────────────────────────────────────────────────────
# System configuration bit masks (from offset 140 — identical to ATW-MBS-02)
# ──────────────────────────────────────────────────────────────────────────────
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
MASK_CIRCUIT1_WIRELESS = 0x0100
MASK_CIRCUIT2_WIRELESS = 0x0200
MASK_CIRCUIT1_WIRELESS_TEMP = 0x0400
MASK_CIRCUIT2_WIRELESS_TEMP = 0x0800

# ──────────────────────────────────────────────────────────────────────────────
# System status bit masks (from offset 166)
# Bits 0-9 are identical to ATW-MBS-02; bits 10-12 are HC-A(16/64)MB extensions.
# ──────────────────────────────────────────────────────────────────────────────
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
# HC-A(16/64)MB extensions
MASK_FORCED_OFF = 0x0400
MASK_DHW_RECIRCULATION = 0x0800
MASK_SOLAR_PUMP = 0x1000

# ──────────────────────────────────────────────────────────────────────────────
# State maps (shared with ATW-MBS-02)
# ──────────────────────────────────────────────────────────────────────────────
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

# HVAC Unit mode values for CONTROL writes
HVAC_UNIT_MODE_COOL = 0
HVAC_UNIT_MODE_HEAT = 1
# HC-A(16/64)MB does not support writing Auto mode directly;
# Auto is indicated in STATUS via bitmask only.
HVAC_UNIT_MODE_AUTO = None

SYSTEM_STATE_ISSUES = {
    1: "desync_warning",
    2: "initializing_warning",
}

# ──────────────────────────────────────────────────────────────────────────────
# Conversion / deserialization functions
# ──────────────────────────────────────────────────────────────────────────────


def convert_signed_16bit(value: int | None) -> int | None:
    """Convert signed 16-bit value using 2's complement for negative values."""
    if value is None:
        return None
    if value == 0xFFFF:
        return None
    if value > 32767:
        value -= 65536
    return int(value)


def convert_from_tenths(value: int | None) -> float | None:
    """Convert values stored in tenths to their actual decimal value."""
    if value is None:
        return None
    if value == 0xFFFF:
        return None
    return float(value) / 10.0


def convert_pressure(value: int | None) -> float | None:
    """Convert pressure value to bar (raw = hundredths of MPa)."""
    if value is None:
        return None
    if value == 0xFFFF:
        return None
    return float(value) / 10.0


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


def deserialize_unit_model(value: int | None) -> str:
    """Convert a raw unit model ID to a model key.

    HC-A(16/64)MB supports more models than ATW-MBS-02:
        0: YUTAKI S
        1: YUTAKI S COMBI
        2: S80
        3: M
        4: SC Lite (HC-A(16/64)MB only)
        5: Yutampo (HC-A(16/64)MB only — identified directly)
        6: YCC (HC-A(16/64)MB only)
    """
    if value is None:
        return "unknown"
    model_map = {
        0: "yutaki_s",
        1: "yutaki_s_combi",
        2: "yutaki_s80",
        3: "yutaki_m",
        4: "yutaki_sc_lite",
        5: "yutampo_r32",
        6: "ycc",
    }
    return model_map.get(value, "unknown")


def deserialize_unit_mode_status(value: int | None) -> int | None:
    """Decode unit mode from STATUS register bitmask.

    HC-A(16/64)MB STATUS register encodes the mode as:
        B0: 0=Cool, 1=Heat
        B1: 0=Normal, 1=Auto

    Returns a unified mode value compatible with ATW-MBS-02:
        0=Cool, 1=Heat, 2=Auto
    """
    if value is None:
        return None
    is_heat = bool(value & 0x01)
    is_auto = bool(value & 0x02)
    if is_auto:
        return 2  # Auto
    return 1 if is_heat else 0  # Heat or Cool


def deserialize_otc_method(value: int | None) -> str | None:
    """Convert a raw OTC method value to an OTC method constant (heating)."""
    if value is None:
        return None
    method_map = {
        0: OTCCalculationMethod.DISABLED,
        1: OTCCalculationMethod.POINTS,
        2: OTCCalculationMethod.GRADIENT,
        3: OTCCalculationMethod.FIX,
    }
    return method_map.get(value)


def serialize_otc_method(value: str) -> int:
    """Convert an OTC method constant to a raw value (heating)."""
    method_map = {
        OTCCalculationMethod.DISABLED: 0,
        OTCCalculationMethod.POINTS: 1,
        OTCCalculationMethod.GRADIENT: 2,
        OTCCalculationMethod.FIX: 3,
    }
    return method_map.get(value, 0)


def deserialize_otc_method_cooling(value: int | None) -> str | None:
    """Convert a raw cooling OTC method value to an OTC method constant.

    HC-A(16/64)MB cooling OTC has only 3 options (no Gradient):
        0=Disabled, 1=Points, 2=Fix
    """
    if value is None:
        return None
    method_map = {
        0: OTCCalculationMethod.DISABLED,
        1: OTCCalculationMethod.POINTS,
        2: OTCCalculationMethod.FIX,
    }
    return method_map.get(value)


def serialize_otc_method_cooling(value: str) -> int:
    """Convert a cooling OTC method constant to a raw value (HC-A(16/64)MB)."""
    method_map = {
        OTCCalculationMethod.DISABLED: 0,
        OTCCalculationMethod.POINTS: 1,
        OTCCalculationMethod.FIX: 2,
    }
    return method_map.get(value, 0)


# ──────────────────────────────────────────────────────────────────────────────
# Address helper
# ──────────────────────────────────────────────────────────────────────────────


def _compute_base(unit_id: int) -> int:
    """Compute the base Modbus address for a given unit ID."""
    return 5000 + (unit_id * 200)


# ──────────────────────────────────────────────────────────────────────────────
# Register map class
# ──────────────────────────────────────────────────────────────────────────────


class HcAMbRegisterMap(HitachiRegisterMap):
    """Register map for the HC-A(16/64)MB gateway.

    All absolute addresses are computed at construction time from the unit_id.
    """

    def __init__(self, unit_id: int = 0) -> None:
        """Initialize the register map for a given unit ID."""
        self._unit_id = unit_id
        self._base = _compute_base(unit_id)
        self._build_registers()

    def _addr(self, offset: int) -> int:
        """Compute absolute address from offset."""
        return self._base + offset

    def _build_registers(self) -> None:
        """Build all register dictionaries with computed absolute addresses."""
        # --- Gateway (STATUS only) ---
        self._register_gateway: dict[str, RegisterDefinition] = {
            "alarm_code": RegisterDefinition(
                self._addr(167), deserializer=deserialize_alarm_code
            ),
            "unit_model": RegisterDefinition(
                self._addr(162), deserializer=deserialize_unit_model
            ),
            "system_config": RegisterDefinition(self._addr(140)),
            "system_status": RegisterDefinition(self._addr(166)),
            "system_state": RegisterDefinition(
                self._addr(145), deserializer=deserialize_system_state
            ),
        }

        # --- Control Unit (mix CONTROL + STATUS) ---
        self._register_control_unit: dict[str, RegisterDefinition] = {
            "unit_power": RegisterDefinition(
                self._addr(100), write_address=self._addr(50)
            ),
            "unit_mode": RegisterDefinition(
                self._addr(101),
                deserializer=deserialize_unit_mode_status,
                write_address=self._addr(51),
            ),
            "operation_state": RegisterDefinition(
                self._addr(141), deserializer=deserialize_operation_state
            ),
            "operation_state_code": RegisterDefinition(self._addr(141)),
            "outdoor_temp": RegisterDefinition(
                self._addr(142), deserializer=convert_signed_16bit
            ),
            "water_inlet_temp": RegisterDefinition(
                self._addr(143), deserializer=convert_signed_16bit
            ),
            "water_outlet_temp": RegisterDefinition(
                self._addr(144), deserializer=convert_signed_16bit
            ),
            "water_target_temp": RegisterDefinition(
                self._addr(163), deserializer=convert_signed_16bit
            ),
            "water_flow": RegisterDefinition(
                self._addr(164), deserializer=convert_from_tenths
            ),
            "pump_speed": RegisterDefinition(self._addr(165)),
            "power_consumption": RegisterDefinition(self._addr(149)),
        }

        # --- Circuit 1 (CONTROL + STATUS) ---
        self._register_circuit_1: dict[str, RegisterDefinition] = {
            "circuit1_power": RegisterDefinition(
                self._addr(102), write_address=self._addr(52)
            ),
            "circuit1_otc_calculation_method_heating": RegisterDefinition(
                self._addr(103),
                deserializer=deserialize_otc_method,
                write_address=self._addr(53),
            ),
            "circuit1_otc_calculation_method_cooling": RegisterDefinition(
                self._addr(104),
                deserializer=deserialize_otc_method_cooling,
                write_address=self._addr(54),
            ),
            "circuit1_max_flow_temp_heating_otc": RegisterDefinition(
                self._addr(105), write_address=self._addr(55)
            ),
            "circuit1_max_flow_temp_cooling_otc": RegisterDefinition(
                self._addr(106), write_address=self._addr(56)
            ),
            "circuit1_eco_mode": RegisterDefinition(
                self._addr(107), write_address=self._addr(57)
            ),
            "circuit1_heat_eco_offset": RegisterDefinition(
                self._addr(108), write_address=self._addr(58)
            ),
            "circuit1_cool_eco_offset": RegisterDefinition(
                self._addr(109), write_address=self._addr(59)
            ),
            "circuit1_thermostat": RegisterDefinition(
                # CONTROL only (offset 60), no STATUS read address
                self._addr(60),
                write_address=self._addr(60),
            ),
            "circuit1_target_temp": RegisterDefinition(
                self._addr(110),
                deserializer=convert_from_tenths,
                write_address=self._addr(61),
            ),
            "circuit1_current_temp": RegisterDefinition(
                self._addr(111),
                deserializer=convert_from_tenths,
                write_address=self._addr(62),
            ),
        }

        # --- Circuit 2 (CONTROL + STATUS, offsets 114-125 / 63-73) ---
        self._register_circuit_2: dict[str, RegisterDefinition] = {
            "circuit2_power": RegisterDefinition(
                self._addr(114), write_address=self._addr(63)
            ),
            "circuit2_otc_calculation_method_heating": RegisterDefinition(
                self._addr(115),
                deserializer=deserialize_otc_method,
                write_address=self._addr(64),
            ),
            "circuit2_otc_calculation_method_cooling": RegisterDefinition(
                self._addr(116),
                deserializer=deserialize_otc_method_cooling,
                write_address=self._addr(65),
            ),
            "circuit2_max_flow_temp_heating_otc": RegisterDefinition(
                self._addr(117), write_address=self._addr(66)
            ),
            "circuit2_max_flow_temp_cooling_otc": RegisterDefinition(
                self._addr(118), write_address=self._addr(67)
            ),
            "circuit2_eco_mode": RegisterDefinition(
                self._addr(119), write_address=self._addr(68)
            ),
            "circuit2_heat_eco_offset": RegisterDefinition(
                self._addr(120), write_address=self._addr(69)
            ),
            "circuit2_cool_eco_offset": RegisterDefinition(
                self._addr(121), write_address=self._addr(70)
            ),
            "circuit2_thermostat": RegisterDefinition(
                self._addr(71),
                write_address=self._addr(71),
            ),
            "circuit2_target_temp": RegisterDefinition(
                self._addr(122),
                deserializer=convert_from_tenths,
                write_address=self._addr(72),
            ),
            "circuit2_current_temp": RegisterDefinition(
                self._addr(123),
                deserializer=convert_from_tenths,
                write_address=self._addr(73),
            ),
        }

        # --- DHW (CONTROL + STATUS) ---
        self._register_dhw: dict[str, RegisterDefinition] = {
            "dhw_power": RegisterDefinition(
                self._addr(126), write_address=self._addr(74)
            ),
            "dhw_target_temp": RegisterDefinition(
                self._addr(127), write_address=self._addr(75)
            ),
            "dhw_boost": RegisterDefinition(
                self._addr(128), write_address=self._addr(76)
            ),
            "dhw_high_demand": RegisterDefinition(
                self._addr(130), write_address=self._addr(78)
            ),
            "dhw_antilegionella": RegisterDefinition(
                self._addr(135), write_address=self._addr(81)
            ),
            "dhw_antilegionella_temp": RegisterDefinition(
                self._addr(136), write_address=self._addr(82)
            ),
            "dhw_current_temp": RegisterDefinition(
                self._addr(131), deserializer=convert_signed_16bit
            ),
            "dhw_antilegionella_status": RegisterDefinition(self._addr(135)),
            "dhw_antilegionella_temp_status": RegisterDefinition(self._addr(136)),
        }

        # --- Pool (CONTROL + STATUS) ---
        # Note: HC-A(16/64)MB pool_target_temp is integer °C (NOT tenths like ATW-MBS-02)
        self._register_pool: dict[str, RegisterDefinition] = {
            "pool_power": RegisterDefinition(
                self._addr(132), write_address=self._addr(79)
            ),
            "pool_target_temp": RegisterDefinition(
                self._addr(133), write_address=self._addr(80)
            ),
            "pool_current_temp": RegisterDefinition(
                self._addr(134), deserializer=convert_signed_16bit
            ),
        }

        # --- Primary Compressor (STATUS only) ---
        # Indoor unit registers (offsets 156-158) provide gas temp, liquid temp, and
        # indoor EVI valve.  Outdoor unit registers (offsets 0-17, section 5.3) provide
        # discharge temp, evaporator temp, frequency, current, and outdoor expansion
        # valve.  Both ranges coexist in the same unit_id block without conflict.
        self._register_primary_compressor: dict[str, RegisterDefinition] = {
            # Indoor unit registers (offsets 156-158)
            "compressor_tg_gas_temp": RegisterDefinition(
                self._addr(156), deserializer=convert_signed_16bit
            ),
            "compressor_ti_liquid_temp": RegisterDefinition(
                self._addr(157), deserializer=convert_signed_16bit
            ),
            "compressor_evi_indoor_expansion_valve_opening": RegisterDefinition(
                self._addr(158)
            ),
            # Outdoor unit registers (offsets 0-17, section 5.3)
            "compressor_td_discharge_temp": RegisterDefinition(
                self._addr(1), deserializer=convert_signed_16bit
            ),
            "compressor_te_evaporator_temp": RegisterDefinition(
                self._addr(2), deserializer=convert_signed_16bit
            ),
            "compressor_current": RegisterDefinition(self._addr(6)),
            "compressor_frequency": RegisterDefinition(self._addr(7)),
            "compressor_evo_outdoor_expansion_valve_opening": RegisterDefinition(
                self._addr(8)
            ),
        }

        # --- Secondary Compressor (STATUS only, R134a data for S80) ---
        self._register_secondary_compressor: dict[str, RegisterDefinition] = {
            "secondary_compressor_discharge_temp": RegisterDefinition(
                self._addr(168), deserializer=convert_signed_16bit
            ),
            "secondary_compressor_suction_temp": RegisterDefinition(
                self._addr(169), deserializer=convert_signed_16bit
            ),
            "secondary_compressor_discharge_pressure": RegisterDefinition(
                self._addr(170), deserializer=convert_pressure
            ),
            "secondary_compressor_suction_pressure": RegisterDefinition(
                self._addr(171), deserializer=convert_pressure
            ),
            "secondary_compressor_frequency": RegisterDefinition(self._addr(172)),
            "secondary_compressor_valve_opening": RegisterDefinition(self._addr(173)),
            "secondary_compressor_current": RegisterDefinition(
                self._addr(174), deserializer=convert_from_tenths
            ),
            "secondary_compressor_retry_code": RegisterDefinition(self._addr(175)),
        }

        # Build combined register map
        self._all_registers: dict[str, RegisterDefinition] = {
            **self._register_gateway,
            **self._register_control_unit,
            **self._register_primary_compressor,
            **self._register_secondary_compressor,
            **self._register_circuit_1,
            **self._register_circuit_2,
            **self._register_dhw,
            **self._register_pool,
        }

        # Writable keys — registers that have a write_address or are CONTROL-only
        self._writable_keys: set[str] = {
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

    # ── Key list properties ──────────────────────────────────────────────────

    @property
    def gateway_keys(self) -> list[str]:
        """Return the list of gateway keys."""
        return list(self._register_gateway.keys())

    @property
    def control_unit_keys(self) -> list[str]:
        """Return the list of control unit keys."""
        return list(self._register_control_unit.keys())

    @property
    def primary_compressor_keys(self) -> list[str]:
        """Return the list of primary compressor keys."""
        return list(self._register_primary_compressor.keys())

    @property
    def secondary_compressor_keys(self) -> list[str]:
        """Return the list of secondary compressor keys."""
        return list(self._register_secondary_compressor.keys())

    @property
    def circuit_1_keys(self) -> list[str]:
        """Return the list of circuit 1 keys."""
        return list(self._register_circuit_1.keys())

    @property
    def circuit_2_keys(self) -> list[str]:
        """Return the list of circuit 2 keys."""
        return list(self._register_circuit_2.keys())

    @property
    def dhw_keys(self) -> list[str]:
        """Return the list of DHW keys."""
        return list(self._register_dhw.keys())

    @property
    def pool_keys(self) -> list[str]:
        """Return the list of pool keys."""
        return list(self._register_pool.keys())

    # ── Interface properties ─────────────────────────────────────────────────

    @property
    def all_registers(self) -> dict[str, RegisterDefinition]:
        """Return all registers in a single map."""
        return self._all_registers

    @property
    def writable_keys(self) -> set[str]:
        """Return the set of writable register keys."""
        return self._writable_keys

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
        """Return the raw value for auto mode (None — HC-A(16/64)MB cannot write Auto)."""
        return HVAC_UNIT_MODE_AUTO

    def serialize_otc_method(self, value: str) -> int:
        """Convert a heating OTC method constant to a raw register value."""
        return serialize_otc_method(value)

    def serialize_otc_method_cooling(self, value: str) -> int:
        """Convert a cooling OTC method constant to a raw register value.

        HC-A(16/64)MB cooling has a different mapping (no Gradient): 0=Disabled, 1=Points, 2=Fix.
        """
        return serialize_otc_method_cooling(value)
