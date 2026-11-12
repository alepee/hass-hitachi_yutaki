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

from dataclasses import dataclass
from typing import Any

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
    unit_model,
)

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
MASKS_CIRCUIT_THERMOSTAT = {
    CIRCUIT_PRIMARY_ID: MASK_CIRCUIT1_THERMOSTAT,
    CIRCUIT_SECONDARY_ID: MASK_CIRCUIT2_THERMOSTAT,
}
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

# HVAC Unit mode values for CONTROL writes
HVAC_UNIT_MODE_COOL = 0
HVAC_UNIT_MODE_HEAT = 1
# HC-A(16/64)MB does not support writing Auto mode directly;
# Auto is indicated in STATUS via bitmask only.
HVAC_UNIT_MODE_AUTO = None

SYSTEM_STATE_ISSUES = {
    1: "desync_warning",
    2: "initializing_warning",
    # 0xFFFF: the gateway answers Modbus but returns no heat pump data at all
    # (every register reads 0xFFFF, field telemetry): treat it as not ready
    # rather than as a healthy state (#404).
    0xFFFF: "no_data_warning",
}

# ──────────────────────────────────────────────────────────────────────────────
# Codecs specific to this map
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HcaUnitMode:
    """Unit mode: read as STATUS bits (offset 101), written as CONTROL (51).

    STATUS encodes B0 = 0 cool / 1 heat and B1 = 0 normal / 1 auto, decoded
    to the ATW-MBS-02 values (0 cool, 1 heat, 2 auto). CONTROL only takes
    0 cool / 1 heat: auto cannot be commanded on this gateway. A word outside
    the two bits (e.g. 0xFFFF, which read as auto before #534) is no mode.
    """

    def decode(self, raw: int) -> int | None:
        """Return 0 cool, 1 heat or 2 auto, or None for an undocumented word."""
        if raw > 0b11:
            return None
        return 2 if raw & 0b10 else raw & 0b01

    def encode(self, value: Any) -> int:
        """Return the CONTROL word for cool (0) or heat (1)."""
        if isinstance(value, bool) or value not in (0, 1):
            raise ValueError(f"not a commandable unit mode: {value!r}")
        return int(value)


HCA_UNIT_MODE = HcaUnitMode()
# Offset 162: S, S Combi, S80, M, SC Lite, Yutampo, YCC.
UNIT_MODEL = unit_model(0, 1, 2, 3, 4, 5, 6)


# ──────────────────────────────────────────────────────────────────────────────
# Address helper
# ──────────────────────────────────────────────────────────────────────────────


def _compute_base(unit_id: int) -> int:
    """Compute the base Modbus address for a given indoor unit ID."""
    return 5000 + (unit_id * 200)


# Outdoor unit register block (section 5.2.3 of the HC-A(16/64)MB datasheet,
# PMML0351 rev.6). This is a separate address range from the indoor unit block
# (section 5.2). Each outdoor refrigerant cycle owns a 100-register block keyed
# on the cycle number (NOT the indoor unit_id): address = 30000 + cycle * 100.
# The cycle is arbitrary and read from the gateway unit table (#353).
_OUTDOOR_UNIT_BASE = 30000
_OUTDOOR_CYCLE_STRIDE = 100


# ──────────────────────────────────────────────────────────────────────────────
# Register map class
# ──────────────────────────────────────────────────────────────────────────────


class HcAMbRegisterMap(HitachiRegisterMap):
    """Register map for the HC-A(16/64)MB gateway.

    All absolute addresses are computed at construction time from the unit_id
    (indoor block) and the outdoor refrigerant cycle (outdoor block).
    """

    def __init__(self, unit_id: int = 0, outdoor_cycle: int | None = None) -> None:
        """Initialize the register map for a given unit ID and outdoor cycle.

        Args:
            unit_id: H-LINK indoor unit id; keys the indoor register block.
            outdoor_cycle: Outdoor refrigerant cycle number; keys the outdoor
                register block. Defaults to 0 (the shared/first block) when
                unknown, preserving the pre-#353 behaviour.

        """
        self._unit_id = unit_id
        self._base = _compute_base(unit_id)
        self._outdoor_cycle = outdoor_cycle if outdoor_cycle is not None else 0
        self._build_registers()

    @property
    def unit_id(self) -> int:
        """Return the gateway slot keying the indoor register block."""
        return self._unit_id

    def _addr(self, offset: int) -> int:
        """Compute absolute address from indoor unit offset."""
        return self._base + offset

    def _outdoor_addr(self, offset: int) -> int:
        """Compute absolute address for outdoor unit registers (section 5.2.3).

        The outdoor register block is keyed on the outdoor refrigerant cycle,
        not the indoor unit_id: a gateway with several independent systems has
        one 100-register block per cycle at 30000 + cycle * 100. The cycle is
        arbitrary (e.g. cycles 0/5/7 for units 0/1/2) and detected from the
        gateway unit table. It defaults to 0 when unknown (#353).
        """
        return (
            _OUTDOOR_UNIT_BASE + (self._outdoor_cycle * _OUTDOOR_CYCLE_STRIDE) + offset
        )

    def _build_registers(self) -> None:
        """Build all register dictionaries with computed absolute addresses."""
        # --- Gateway (STATUS only) ---
        self._register_gateway: dict[str, RegisterDefinition] = {
            "alarm_code": RegisterDefinition(
                self._addr(167),
                ALARM_CODE,
            ),
            "unit_model": RegisterDefinition(
                self._addr(162),
                UNIT_MODEL,
            ),
            # 0xFFFF is a garbage read, not a configuration (#404).
            "system_config": RegisterDefinition(
                self._addr(140),
                UNSIGNED,
            ),
            "system_status": RegisterDefinition(self._addr(166), UNSIGNED),
            "system_state": RegisterDefinition(
                self._addr(145),
                SYSTEM_STATE,
            ),
            # "LCD Central Mode" (139): 0 local, 1 air, 2 water, 3 full.
            "central_control_mode": RegisterDefinition(
                self._addr(139), CENTRAL_CONTROL_MODE
            ),
        }

        # --- Control Unit (mix CONTROL + STATUS) ---
        self._register_control_unit: dict[str, RegisterDefinition] = {
            "unit_power": RegisterDefinition(
                self._addr(100), SWITCH, write_address=self._addr(50)
            ),
            "unit_mode": RegisterDefinition(
                self._addr(101),
                HCA_UNIT_MODE,
                write_address=self._addr(51),
            ),
            "operation_state": RegisterDefinition(
                self._addr(141),
                OPERATION_STATE,
            ),
            "operation_state_code": RegisterDefinition(self._addr(141), UNSIGNED),
            "outdoor_temp": RegisterDefinition(
                self._addr(142),
                SIGNED,
            ),
            "water_inlet_temp": RegisterDefinition(
                self._addr(143),
                SIGNED,
            ),
            "water_outlet_temp": RegisterDefinition(
                self._addr(144),
                SIGNED,
            ),
            "water_outlet_2_temp": RegisterDefinition(
                self._addr(154),
                SIGNED,
                sentinel_values=frozenset({-127}),
            ),
            "water_outlet_3_temp": RegisterDefinition(
                self._addr(155),
                SIGNED,
                sentinel_values=frozenset({-127}),
            ),
            "water_target_temp": RegisterDefinition(
                self._addr(163),
                SIGNED,
            ),
            "water_flow": RegisterDefinition(
                self._addr(164),
                TENTHS,
            ),
            "pump_speed": RegisterDefinition(self._addr(165), UNSIGNED),
            # Unit board (PCB) and controller (LCD) software numbers, read-only.
            # 0xFFFF is a garbage read, not a version (#404).
            "software_pcb": RegisterDefinition(
                self._addr(146),
                UNSIGNED,
            ),
            "software_lcd": RegisterDefinition(
                self._addr(147),
                UNSIGNED,
            ),
        }

        # --- Circuit 1 (CONTROL + STATUS) ---
        self._register_circuit_1: dict[str, RegisterDefinition] = {
            "circuit1_power": RegisterDefinition(
                self._addr(102), SWITCH, write_address=self._addr(52)
            ),
            "circuit1_otc_calculation_method_heating": RegisterDefinition(
                self._addr(103),
                OTC_METHOD_HEATING,
                write_address=self._addr(53),
            ),
            "circuit1_otc_calculation_method_cooling": RegisterDefinition(
                self._addr(104),
                OTC_METHOD_COOLING,
                write_address=self._addr(54),
            ),
            "circuit1_max_flow_temp_heating_otc": RegisterDefinition(
                self._addr(105), UNSIGNED, write_address=self._addr(55)
            ),
            "circuit1_max_flow_temp_cooling_otc": RegisterDefinition(
                self._addr(106), UNSIGNED, write_address=self._addr(56)
            ),
            "circuit1_eco_mode": RegisterDefinition(
                self._addr(107), SWITCH, write_address=self._addr(57)
            ),
            "circuit1_heat_eco_offset": RegisterDefinition(
                self._addr(108), UNSIGNED, write_address=self._addr(58)
            ),
            "circuit1_cool_eco_offset": RegisterDefinition(
                self._addr(109), UNSIGNED, write_address=self._addr(59)
            ),
            "circuit1_thermostat": RegisterDefinition(
                # CONTROL only (offset 60), no STATUS read address.
                # 0xFFFF is a garbage read, not "enabled" (#404).
                self._addr(60),
                SWITCH,
                write_address=self._addr(60),
            ),
            "circuit1_target_temp": RegisterDefinition(
                self._addr(110),
                TENTHS,
                write_address=self._addr(61),
            ),
            "circuit1_current_temp": RegisterDefinition(
                self._addr(111),
                TENTHS,
                write_address=self._addr(62),
            ),
        }

        # --- Circuit 2 (CONTROL + STATUS, offsets 114-125 / 63-73) ---
        self._register_circuit_2: dict[str, RegisterDefinition] = {
            "circuit2_power": RegisterDefinition(
                self._addr(114), SWITCH, write_address=self._addr(63)
            ),
            "circuit2_otc_calculation_method_heating": RegisterDefinition(
                self._addr(115),
                OTC_METHOD_HEATING,
                write_address=self._addr(64),
            ),
            "circuit2_otc_calculation_method_cooling": RegisterDefinition(
                self._addr(116),
                OTC_METHOD_COOLING,
                write_address=self._addr(65),
            ),
            "circuit2_max_flow_temp_heating_otc": RegisterDefinition(
                self._addr(117), UNSIGNED, write_address=self._addr(66)
            ),
            "circuit2_max_flow_temp_cooling_otc": RegisterDefinition(
                self._addr(118), UNSIGNED, write_address=self._addr(67)
            ),
            "circuit2_eco_mode": RegisterDefinition(
                self._addr(119), SWITCH, write_address=self._addr(68)
            ),
            "circuit2_heat_eco_offset": RegisterDefinition(
                self._addr(120), UNSIGNED, write_address=self._addr(69)
            ),
            "circuit2_cool_eco_offset": RegisterDefinition(
                self._addr(121), UNSIGNED, write_address=self._addr(70)
            ),
            "circuit2_thermostat": RegisterDefinition(
                self._addr(71),
                SWITCH,
                write_address=self._addr(71),
            ),
            "circuit2_target_temp": RegisterDefinition(
                self._addr(122),
                TENTHS,
                write_address=self._addr(72),
            ),
            "circuit2_current_temp": RegisterDefinition(
                self._addr(123),
                TENTHS,
                write_address=self._addr(73),
            ),
            # "Mixing Valve Opening" (160, %), circuit 2 only, read-only.
            "circuit2_mixing_valve_position": RegisterDefinition(
                self._addr(160),
                UNSIGNED,
            ),
        }

        # --- DHW (CONTROL + STATUS) ---
        self._register_dhw: dict[str, RegisterDefinition] = {
            "dhw_power": RegisterDefinition(
                self._addr(126), SWITCH, write_address=self._addr(74)
            ),
            "dhw_target_temp": RegisterDefinition(
                self._addr(127), UNSIGNED, write_address=self._addr(75)
            ),
            "dhw_boost": RegisterDefinition(
                self._addr(128), SWITCH, write_address=self._addr(76)
            ),
            "dhw_high_demand": RegisterDefinition(
                self._addr(130), SWITCH, write_address=self._addr(78)
            ),
            "dhw_demand_mode": RegisterDefinition(self._addr(130), SWITCH),
            "dhw_antilegionella": RegisterDefinition(
                self._addr(135), SWITCH, write_address=self._addr(81)
            ),
            "dhw_antilegionella_temp": RegisterDefinition(
                self._addr(136), UNSIGNED, write_address=self._addr(82)
            ),
            "dhw_current_temp": RegisterDefinition(
                self._addr(131),
                SIGNED,
                sentinel_values=frozenset({-67}),
            ),
            "dhw_antilegionella_status": RegisterDefinition(self._addr(135), SWITCH),
            "dhw_antilegionella_temp_status": RegisterDefinition(
                self._addr(136), UNSIGNED
            ),
        }

        # --- Pool (CONTROL + STATUS) ---
        # Note: pool_target_temp is integer °C (0~80), no tenths conversion
        self._register_pool: dict[str, RegisterDefinition] = {
            "pool_power": RegisterDefinition(
                self._addr(132), SWITCH, write_address=self._addr(79)
            ),
            "pool_target_temp": RegisterDefinition(
                self._addr(133), UNSIGNED, write_address=self._addr(80)
            ),
            "pool_current_temp": RegisterDefinition(
                self._addr(134),
                SIGNED,
                sentinel_values=frozenset({-127}),
            ),
        }

        # --- Primary Compressor (STATUS only) ---
        # Indoor unit registers (offsets 156-158, section 5.2) provide gas temp,
        # liquid temp, and indoor EVI valve — addressed from the indoor unit base.
        # Outdoor unit registers (offsets 0-17, section 5.2.3) provide discharge
        # temp, evaporator temp, frequency, current, and outdoor expansion valve
        # — addressed from a per-cycle base (30000 + outdoor_cycle * 100).
        self._register_primary_compressor: dict[str, RegisterDefinition] = {
            # Indoor unit registers (section 5.2, offsets 156-158)
            "compressor_tg_gas_temp": RegisterDefinition(
                self._addr(156),
                SIGNED,
            ),
            "compressor_ti_liquid_temp": RegisterDefinition(
                self._addr(157),
                SIGNED,
            ),
            "compressor_evi_indoor_expansion_valve_opening": RegisterDefinition(
                self._addr(158), UNSIGNED
            ),
            # Outdoor unit registers (section 5.3, base 30000)
            "compressor_td_discharge_temp": RegisterDefinition(
                self._outdoor_addr(1),
                SIGNED,
            ),
            "compressor_te_evaporator_temp": RegisterDefinition(
                self._outdoor_addr(2),
                SIGNED,
            ),
            "compressor_current": RegisterDefinition(self._outdoor_addr(6), UNSIGNED),
            "compressor_frequency": RegisterDefinition(self._outdoor_addr(7), UNSIGNED),
            "compressor_evo_outdoor_expansion_valve_opening": RegisterDefinition(
                self._outdoor_addr(8), UNSIGNED
            ),
        }

        # --- Secondary Compressor (STATUS only, R134a data for S80) ---
        self._register_secondary_compressor: dict[str, RegisterDefinition] = {
            "secondary_compressor_discharge_temp": RegisterDefinition(
                self._addr(168),
                SIGNED,
            ),
            "secondary_compressor_suction_temp": RegisterDefinition(
                self._addr(169),
                SIGNED,
            ),
            "secondary_compressor_discharge_pressure": RegisterDefinition(
                self._addr(170),
                TENTHS,
            ),
            "secondary_compressor_suction_pressure": RegisterDefinition(
                self._addr(171),
                TENTHS,
            ),
            "secondary_compressor_frequency": RegisterDefinition(
                self._addr(172), UNSIGNED
            ),
            "secondary_compressor_valve_opening": RegisterDefinition(
                self._addr(173), UNSIGNED
            ),
            "secondary_compressor_current": RegisterDefinition(
                self._addr(174),
                TENTHS,
            ),
            "secondary_compressor_retry_code": RegisterDefinition(
                self._addr(175), UNSIGNED
            ),
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
        """Return the raw value for auto mode (None — HC-A(16/64)MB cannot write Auto)."""
        return HVAC_UNIT_MODE_AUTO
