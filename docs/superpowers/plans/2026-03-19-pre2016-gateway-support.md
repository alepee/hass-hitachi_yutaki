# Pre-2016 ATW-MBS-02 Gateway Support — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read support for Before Line-up 2016 ATW-MBS-02 units as a third gateway type, plus a model decoder tool and scanner support.

**Architecture:** A new `AtwMbs02Pre2016RegisterMap` class in its own file, registered as a third gateway in `GATEWAY_INFO`. The config flow offers 3 gateway choices. The scanner auto-detects before-2016 units. A static HTML tool helps users identify their hardware generation.

**Tech Stack:** Python (HA custom component), vanilla HTML/CSS/JS (decoder tool)

**Spec:** `docs/superpowers/specs/2026-03-19-pre2016-gateway-support-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `custom_components/hitachi_yutaki/api/modbus/registers/atw_mbs_02_pre2016.py` | Before-2016 register map (addresses, masks, conversions) |
| Modify | `custom_components/hitachi_yutaki/api/__init__.py` | Add gateway info + factory case |
| Modify | `custom_components/hitachi_yutaki/translations/en.json` | Add gateway label + description |
| Modify | `scripts/scan_gateway.py` | Before-2016 detection, annotation, recap |
| Create | `docs/tools/model-decoder.html` | Interactive model decoder (GitHub Pages) |
| Create | `tests/api/modbus/registers/test_atw_mbs_02_pre2016.py` | Register map unit tests |
| Modify | `tests/api/modbus/registers/test_compatibility.py` | Cross-gateway key compatibility |

---

### Task 1: Create the Before-2016 register map

**Files:**
- Create: `custom_components/hitachi_yutaki/api/modbus/registers/atw_mbs_02_pre2016.py`

This is the core file. It follows the exact same pattern as `atw_mbs_02.py` but with Before-2016 addresses from PMML0419A Section 5.2.

- [ ] **Step 1: Create register map file with imports, masks, and state maps**

```python
"""Register map for the ATW-MBS-02 gateway (Before Line-up 2016)."""

from ....const import (
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    OTCCalculationMethod,
)
from . import HitachiRegisterMap, RegisterDefinition

# System configuration bit masks (from register 1075, address 1074)
# Same bit order as 2016 but only 8 bits (no wireless settings)
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

# System status 2 bit masks (from register 1223, address 1222)
# Same as 2016 but bit 9 is "Tarrif input enable" instead of "Smart function"
MASK_DEFROST = 0x0001
MASK_SOLAR = 0x0002
MASK_PUMP1 = 0x0004
MASK_PUMP2 = 0x0008
MASK_PUMP3 = 0x0010
MASK_COMPRESSOR = 0x0020
MASK_BOILER = 0x0040
MASK_DHW_HEATER = 0x0080
MASK_SPACE_HEATER = 0x0100
MASK_TARIFF_INPUT = 0x0200

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

# HVAC Unit mode values — NO Auto mode in before-2016
HVAC_UNIT_MODE_COOL = 0
HVAC_UNIT_MODE_HEAT = 1
```

Reference: `atw_mbs_02.py` lines 1-70 for structure. The masks and state maps are identical to 2016 except system_config has only 8 bits and bit 9 of system_status is "Tarrif input" instead of "Smart function".

- [ ] **Step 2: Add conversion functions**

Reuse the same conversion functions from the 2016 map — they are identical (signed 16-bit, tenths, pressure, operation state, alarm code, system state, unit model, OTC methods). Import them directly rather than duplicating:

```python
# Reuse conversion functions from 2016 map — they are identical
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


def deserialize_unit_model_pre2016(value: int | None) -> str:
    """Convert a raw unit model ID to a model key (before-2016).

    Before-2016 only supports 2 models:
        0: YUTAKI S
        1: YUTAKI S COMBI
    """
    if value is None:
        return "unknown"
    model_map = {
        0: "yutaki_s",
        1: "yutaki_s_combi",
    }
    return model_map.get(value, "unknown")
```

- [ ] **Step 3: Add register dictionaries with Before-2016 addresses**

All addresses from PMML0419A Section 5.2. Key differences from 2016:

```python
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
        1199,  # Water outlet hp — before-2016 servicing
        deserializer=convert_signed_16bit,
        fallback=RegisterDefinition(1080, deserializer=convert_signed_16bit),
    ),
    "water_target_temp": RegisterDefinition(1218, deserializer=convert_signed_16bit),
    "water_flow": RegisterDefinition(1220, deserializer=convert_from_tenths),
    "pump_speed": RegisterDefinition(1221),
    "power_consumption": RegisterDefinition(1098),
}

REGISTER_PRIMARY_COMPRESSOR = {
    "compressor_tg_gas_temp": RegisterDefinition(1205, deserializer=convert_signed_16bit),
    "compressor_ti_liquid_temp": RegisterDefinition(1206, deserializer=convert_signed_16bit),
    "compressor_td_discharge_temp": RegisterDefinition(1207, deserializer=convert_signed_16bit),
    "compressor_te_evaporator_temp": RegisterDefinition(1208, deserializer=convert_signed_16bit),
    "compressor_evi_indoor_expansion_valve_opening": RegisterDefinition(1209),
    "compressor_evo_outdoor_expansion_valve_opening": RegisterDefinition(1210),
    "compressor_frequency": RegisterDefinition(1211),
    "compressor_current": RegisterDefinition(1213),
}

REGISTER_SECONDARY_COMPRESSOR = {
    "secondary_compressor_discharge_temp": RegisterDefinition(1224, deserializer=convert_signed_16bit),
    "secondary_compressor_suction_temp": RegisterDefinition(1225, deserializer=convert_signed_16bit),
    "secondary_compressor_discharge_pressure": RegisterDefinition(1226, deserializer=convert_pressure),
    "secondary_compressor_suction_pressure": RegisterDefinition(1227, deserializer=convert_pressure),
    "secondary_compressor_frequency": RegisterDefinition(1228),
    "secondary_compressor_valve_opening": RegisterDefinition(1229),
    "secondary_compressor_current": RegisterDefinition(1230, deserializer=convert_from_tenths),
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
    "circuit1_max_flow_temp_heating_otc": RegisterDefinition(1007),
    "circuit1_max_flow_temp_cooling_otc": RegisterDefinition(1008),
    "circuit1_thermostat": RegisterDefinition(1029),
    "circuit1_target_temp": RegisterDefinition(1005, deserializer=convert_from_tenths),
    "circuit1_current_temp": RegisterDefinition(1006, deserializer=convert_from_tenths),
}

REGISTER_CIRCUIT_2 = {
    "circuit2_power": RegisterDefinition(1009),
    "circuit2_otc_calculation_method_heating": RegisterDefinition(
        1010, deserializer=deserialize_otc_method_heating
    ),
    "circuit2_otc_calculation_method_cooling": RegisterDefinition(
        1011, deserializer=deserialize_otc_method_cooling
    ),
    "circuit2_max_flow_temp_heating_otc": RegisterDefinition(1014),
    "circuit2_max_flow_temp_cooling_otc": RegisterDefinition(1015),
    "circuit2_thermostat": RegisterDefinition(1029),
    "circuit2_target_temp": RegisterDefinition(1012, deserializer=convert_from_tenths),
    "circuit2_current_temp": RegisterDefinition(1013, deserializer=convert_from_tenths),
}

REGISTER_DHW = {
    "dhw_power": RegisterDefinition(1016),
    "dhw_target_temp": RegisterDefinition(1017),
    "dhw_current_temp": RegisterDefinition(1075, deserializer=convert_signed_16bit),
    "dhw_antilegionella": RegisterDefinition(1020),
    "dhw_antilegionella_temp": RegisterDefinition(1021),
    "dhw_antilegionella_status": RegisterDefinition(1069),
    "dhw_antilegionella_temp_status": RegisterDefinition(1070),
}

REGISTER_POOL = {
    "pool_power": RegisterDefinition(1018),
    "pool_target_temp": RegisterDefinition(1019),
    "pool_current_temp": RegisterDefinition(1076, deserializer=convert_signed_16bit),
}
```

Notes:
- Before-2016 has NO `dhw_boost` or `dhw_high_demand` registers (these are `Space mode` and `DHW Mode` at different addresses with different semantics: addr 1027=Space mode 0:Comfort/1:ECO, addr 1028=DHW Mode 0:Standard/1:High demand). For Phase 1 (read), we omit these. Phase 2 will address the mapping.
- Before-2016 has NO `circuit*_eco_mode`, `circuit*_heat_eco_offset`, `circuit*_cool_eco_offset` registers.
- Before-2016 circuit1 thermostat and circuit2 thermostat share the same register 1030 (addr 1029 = "Room Thermostat available" 0:No/1:Available).
- Servicing registers are shifted by 1: compressor temps at 1205-1208 (vs 1206-1209 in 2016), etc.
- `water_outlet_temp` uses servicing register 1199 (water outlet hp) with fallback to status 1080.
- `system_state` is at 1083 (H-LINK communication state) — maps 0:No alarm=synchronized, 1:No comm=desynchronized, 2:Data init=initializing.
- `power_consumption` stays at 1098 (same address in before-2016 servicing: "Unit Capacity" at reg 1099 addr 1098 — but this is actually "Unit Capacity" not "Power consumption"; need to verify with tester. For now keep same key for compatibility).

- [ ] **Step 4: Add ALL_REGISTERS, WRITABLE_KEYS (empty for Phase 1), and SYSTEM_STATE_ISSUES**

```python
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

# Phase 1: read-only — no writable keys
WRITABLE_KEYS: set[str] = set()

SYSTEM_STATE_ISSUES = {
    1: "desync_warning",
    2: "initializing_warning",
}
```

- [ ] **Step 5: Implement the `AtwMbs02Pre2016RegisterMap` class**

Follow the exact same pattern as `AtwMbs02RegisterMap` in `atw_mbs_02.py` (lines 411-559). Implement all abstract properties from `HitachiRegisterMap`. Key difference: `hvac_unit_mode_auto` returns `None` (no Auto mode).

For `mask_smart_function`, return `MASK_TARIFF_INPUT` (same bit position 0x0200, different label but same functional role as a status indicator).

- [ ] **Step 6: Verify file compiles**

Run: `python -c "from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02_pre2016 import AtwMbs02Pre2016RegisterMap; print('OK')"`

- [ ] **Step 7: Commit**

```bash
git add custom_components/hitachi_yutaki/api/modbus/registers/atw_mbs_02_pre2016.py
git commit -m "feat: add Before Line-up 2016 ATW-MBS-02 register map

Register definitions for Gen 1 Yutaki S and S Combi units based on
PMML0419A Section 5.2. Phase 1: read-only (no writable keys).

Refs: #248"
```

---

### Task 2: Register the new gateway

**Files:**
- Modify: `custom_components/hitachi_yutaki/api/__init__.py`
- Modify: `custom_components/hitachi_yutaki/translations/en.json`

- [ ] **Step 1: Update `api/__init__.py`**

Add import and gateway info entry:

```python
# Add import at top
from .modbus.registers.atw_mbs_02_pre2016 import AtwMbs02Pre2016RegisterMap

# Add to GATEWAY_INFO dict
"modbus_atw_mbs_02_pre2016": GatewayInfo(
    manufacturer="Hitachi",
    model="ATW-MBS-02 (Before Line-up 2016)",
    client_class=ModbusApiClient,
),

# Update create_register_map()
def create_register_map(
    gateway_type: str, unit_id: int = DEFAULT_UNIT_ID
) -> HitachiRegisterMap | None:
    if gateway_type == "modbus_hc_a_mb":
        return HcAMbRegisterMap(unit_id=unit_id)
    if gateway_type == "modbus_atw_mbs_02_pre2016":
        return AtwMbs02Pre2016RegisterMap()
    return None
```

- [ ] **Step 2: Update `translations/en.json`**

Add the new gateway option in the `selector.gateway_type.options` object:

```json
"modbus_atw_mbs_02_pre2016": "Modbus ATW-MBS-02 (Before Line-up 2016)"
```

Also add a description hint in the config flow step if needed to mention the model decoder tool.

- [ ] **Step 3: Run `make check` to verify**

- [ ] **Step 4: Commit**

```bash
git add custom_components/hitachi_yutaki/api/__init__.py custom_components/hitachi_yutaki/translations/en.json
git commit -m "feat: register Before-2016 ATW-MBS-02 as third gateway type

Adds gateway info, factory method, and translation string for the
pre-2016 register map. The config flow now offers 3 gateway choices.

Refs: #248"
```

---

### Task 3: Unit tests for the register map

**Files:**
- Create: `tests/api/modbus/registers/test_atw_mbs_02_pre2016.py`
- Modify: `tests/api/modbus/registers/test_compatibility.py`

- [ ] **Step 1: Create register map tests**

```python
"""Tests for the ATW-MBS-02 Before Line-up 2016 register map."""

from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02_pre2016 import (
    AtwMbs02Pre2016RegisterMap,
    deserialize_unit_model_pre2016,
)


class TestPre2016RegisterMap:
    """Test Before-2016 register map structure."""

    def test_instantiation(self):
        """Register map can be instantiated."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        assert reg_map is not None

    def test_all_registers_populated(self):
        """All register groups contribute to all_registers."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        assert "unit_power" in reg_map.all_registers
        assert "outdoor_temp" in reg_map.all_registers
        assert "dhw_current_temp" in reg_map.all_registers
        assert "compressor_frequency" in reg_map.all_registers
        assert "unit_model" in reg_map.all_registers

    def test_no_auto_mode(self):
        """Before-2016 does not support Auto mode."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        assert reg_map.hvac_unit_mode_auto is None
        assert reg_map.hvac_unit_mode_cool == 0
        assert reg_map.hvac_unit_mode_heat == 1

    def test_writable_keys_empty_phase1(self):
        """Phase 1 is read-only."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        assert len(reg_map.writable_keys) == 0

    def test_key_addresses_differ_from_2016(self):
        """Verify key registers are at before-2016 addresses, not 2016."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        regs = reg_map.all_registers
        # Status registers shifted vs 2016
        assert regs["operation_state"].address == 1077  # 2016: 1090
        assert regs["outdoor_temp"].address == 1078  # 2016: 1091
        assert regs["water_inlet_temp"].address == 1079  # 2016: 1092
        # Servicing registers shifted by 1
        assert regs["unit_model"].address == 1217  # 2016: 1218
        # DHW at different control address
        assert regs["dhw_power"].address == 1016  # 2016: 1024
        assert regs["dhw_current_temp"].address == 1075  # 2016: 1080
        # System config at different address
        assert regs["system_config"].address == 1074  # 2016: 1089


class TestPre2016UnitModelDeserializer:
    """Test before-2016 unit model deserializer."""

    def test_known_models(self):
        assert deserialize_unit_model_pre2016(0) == "yutaki_s"
        assert deserialize_unit_model_pre2016(1) == "yutaki_s_combi"

    def test_unknown_model(self):
        assert deserialize_unit_model_pre2016(2) == "unknown"
        assert deserialize_unit_model_pre2016(99) == "unknown"

    def test_none(self):
        assert deserialize_unit_model_pre2016(None) == "unknown"
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/api/modbus/registers/test_atw_mbs_02_pre2016.py -v`

- [ ] **Step 3: Add cross-gateway compatibility tests**

In `test_compatibility.py`, add `AtwMbs02Pre2016RegisterMap` to the shared key tests. The before-2016 map uses the same key names but different addresses — the compatibility tests verify key naming consistency.

Note: before-2016 does NOT have `dhw_boost`, `dhw_high_demand`, `circuit*_eco_mode` keys. Adjust the shared DHW keys test to only check keys that exist in all three maps, and add a separate test for before-2016-specific omissions.

- [ ] **Step 4: Run full test suite**

Run: `make test`

- [ ] **Step 5: Commit**

```bash
git add tests/api/modbus/registers/test_atw_mbs_02_pre2016.py tests/api/modbus/registers/test_compatibility.py
git commit -m "test: add Before-2016 register map and compatibility tests

Refs: #248"
```

---

### Task 4: Update the scanner script

**Files:**
- Modify: `scripts/scan_gateway.py`

- [ ] **Step 1: Add before-2016 register map to bootstrap**

In `_bootstrap_register_maps()`, load the third register file:

```python
pre2016_mod = _load_module_from_file(
    f"{reg_pkg_name}.atw_mbs_02_pre2016",
    _REGISTERS_DIR / "atw_mbs_02_pre2016.py",
    package=reg_pkg_name,
)
return atw_mod.AtwMbs02RegisterMap, hc_mod.HcAMbRegisterMap, pre2016_mod.AtwMbs02Pre2016RegisterMap
```

- [ ] **Step 2: Add gateway constant and CLI option**

```python
GATEWAY_ATW_MBS_02_PRE2016 = "atw-mbs-02-pre2016"
```

Add to `--gateway` choices in `parse_args()`.

- [ ] **Step 3: Update `detect_gateway()` with before-2016 probe**

After the ATW-MBS-02 2016 check fails (value at 1218 not in 0-3), try address 1217:

```python
# Try ATW-MBS-02 before-2016: unit_model at address 1217
try:
    result = client.read_holding_registers(
        address=1217, count=1, device_id=device_id
    )
    if not result.isError() and 0 <= result.registers[0] <= 1:
        return GATEWAY_ATW_MBS_02_PRE2016
except Exception:
    pass
```

- [ ] **Step 4: Update register map instantiation and system recap**

In `main()`, instantiate `AtwMbs02Pre2016RegisterMap()` when the detected gateway is before-2016.

Update `print_system_recap()` with before-2016 addresses:

```python
elif gateway_type == GATEWAY_ATW_MBS_02_PRE2016:
    addr_model = 1217
    addr_config = 1074
    addr_status = 1222
    addr_state = 1083
    addr_op_state = 1077
    addr_mode = 1001
    addr_outdoor = 1078
    addr_inlet = 1079
    addr_outlet = 1080
    addr_target = 1218
    addr_flow = 1220
    addr_power = 1098
```

- [ ] **Step 5: Test the scanner locally**

Run: `uv run python scripts/scan_gateway.py --help` (verify the new `--gateway` option appears)

- [ ] **Step 6: Commit**

```bash
git add scripts/scan_gateway.py
git commit -m "feat(scanner): add Before-2016 ATW-MBS-02 detection and annotation

Auto-detects before-2016 units by probing unit_model at address 1217.
Annotates scans with correct register names and system recap addresses.

Refs: #248"
```

---

### Task 5: Model decoder HTML tool

**Files:**
- Create: `docs/tools/model-decoder.html`

- [ ] **Step 1: Create the HTML page with cascading selectors**

A self-contained HTML file with:
- Cascading `<select>` elements: Prefix → Capacity → Suffix → Tank
- Nomenclature data embedded as JS objects (from `model-nomenclature.md`)
- Result display: family, generation, refrigerant, register map, config flow recommendation
- Clean styling, no external dependencies
- Link back to the full nomenclature documentation

The selectors filter options based on previous selections. The result appears as soon as the suffix is selected (tank is optional for determining the register map).

- [ ] **Step 2: Test locally**

Open `docs/tools/model-decoder.html` in a browser and verify:
- Selecting RWD → NWSE shows "Before Line-up 2016"
- Selecting RWD → NW1E shows "Line-up 2016"
- Selecting RASM → VNE shows "Before Line-up 2016"
- Selecting RWH → anything shows "Line-up 2016"

- [ ] **Step 3: Commit**

```bash
git add docs/tools/model-decoder.html
git commit -m "feat: add interactive model decoder tool for GitHub Pages

Helps users identify their hardware generation and which gateway to
select in the config flow. Uses cascading selectors based on the
Hitachi model nomenclature.

Refs: #248"
```

---

### Task 6: Final verification and documentation

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Run full test suite**

Run: `make test`
Expected: All tests pass (existing + new)

- [ ] **Step 2: Run lint/format**

Run: `make check`
Expected: All checks pass

- [ ] **Step 3: Update CHANGELOG.md**

Add under `[Unreleased]`:

```markdown
### Added
- Support for Before Line-up 2016 ATW-MBS-02 gateway (Gen 1 Yutaki S and S Combi units) — read-only sensors (#248)
- Interactive model decoder tool to identify hardware generation (`docs/tools/model-decoder.html`)
- Scanner auto-detection and annotation for before-2016 units
```

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: update changelog for Before-2016 gateway support

Refs: #248"
```

---

## Verification Checklist

- [ ] `AtwMbs02Pre2016RegisterMap` instantiates and passes all tests
- [ ] Config flow shows 3 gateway options
- [ ] Cross-gateway key compatibility tests pass
- [ ] Scanner detects before-2016 and annotates correctly
- [ ] Model decoder tool works in browser
- [ ] `make test` passes (all existing + new tests)
- [ ] `make check` passes (lint + format)
- [ ] CHANGELOG updated
