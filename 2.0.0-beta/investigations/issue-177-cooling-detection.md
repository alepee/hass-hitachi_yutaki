# Issue #177: Cooling Features Not Working

## Summary

**Status**: ✅ Fixed in beta.8
**Commit**: `6183bee`
**Root Cause**: System_config bitmask order incorrectly swapped during v2.0.0 refactoring

## Problem Description

Cooling features that were available and working in v1.9.x are not functioning in v2.0.0 beta releases. The integration fails to detect cooling hardware and does not create cooling-related entities.

### Symptoms Reported by @tijmenvanstraten

- `select.control_unit_operation_mode` only shows "Auto" and "Heat" (no "Cool" option)
- Cooling thermal power sensors not created
- Cooling energy consumption sensors not created
- However, when manually switching to cooling mode on the heat pump:
  - `sensor.control_unit_operation_state` correctly shows "Cooling_OFF"
  - `climate.circuit_1_climate_control` correctly shows "Cool" mode
  - Temperatures are reported correctly

This indicated the **state reading** worked, but **capability detection** was broken.

## Investigation

### Data Source

Modbus dump from discussion #115 provided by @tijmenvanstraten (Yutaki S Combi with optional cooling).

### Key Finding

Register 1089 (`system_config`) value: **21** (decimal) = `0b00010101`

### ATW-MBS-02 Documentation (Register 1089)

| Bit | Mask | Meaning |
|-----|------|---------|
| 0 | 0x0001 | Circuit 1 Heating |
| 1 | 0x0002 | Circuit 2 Heating |
| 2 | 0x0004 | Circuit 1 Cooling |
| 3 | 0x0008 | Circuit 2 Cooling |
| 4 | 0x0010 | DHW |
| 5 | 0x0020 | Pool |

### v1.9.x Implementation (Correct)

```python
# const.py in v1.9.4
MASK_CIRCUIT1_HEATING = 0x0001  # Bit 0
MASK_CIRCUIT2_HEATING = 0x0002  # Bit 1
MASK_CIRCUIT1_COOLING = 0x0004  # Bit 2
MASK_CIRCUIT2_COOLING = 0x0008  # Bit 3
```

### v2.0.0 Implementation (Incorrect)

```python
# api/modbus/registers/atw_mbs_02.py (BEFORE fix)
MASKS_CIRCUIT = {
    (CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING): 0x0001,  # OK
    (CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING): 0x0002,  # WRONG - should be 0x0004
    (CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING): 0x0004,  # WRONG - should be 0x0002
    (CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING): 0x0008,  # OK
}
```

### Decoding with Incorrect Masks

Value 21 (`0b10101`) with v2.0.0 masks:
- Circuit 1 Heating (0x0001): ✓ True
- Circuit 1 Cooling (0x0002): ✗ False (wrong!)
- Circuit 2 Heating (0x0004): ✓ True (wrong!)
- DHW (0x0010): ✓ True

**Result**: Integration thought user had Circuit 1 + Circuit 2 (heating only), no cooling.

### Decoding with Correct Masks

Value 21 (`0b10101`) with v1.9.x masks:
- Circuit 1 Heating (0x0001): ✓ True
- Circuit 2 Heating (0x0002): ✗ False
- Circuit 1 Cooling (0x0004): ✓ True
- DHW (0x0010): ✓ True

**Result**: Correctly detects Circuit 1 (Heating + Cooling) + DHW.

## Fix

### Commit `6183bee`

```python
# api/modbus/registers/atw_mbs_02.py (AFTER fix)
# System configuration bit masks (from register 1089)
# Bit order per Modbus documentation:
#   Bit 0: Circuit 1 Heating, Bit 1: Circuit 2 Heating
#   Bit 2: Circuit 1 Cooling, Bit 3: Circuit 2 Cooling
MASKS_CIRCUIT = {
    (CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING): 0x0001,
    (CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING): 0x0002,
    (CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING): 0x0004,
    (CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING): 0x0008,
}
```

## Impact

After fix, users with cooling hardware will have:
- "Cool" option in `select.control_unit_operation_mode`
- `thermal_power_cooling` sensor
- `thermal_energy_cooling_daily` sensor
- `thermal_energy_cooling_total` sensor
- Proper HVAC modes in climate entities

## Related Files

- `api/modbus/registers/atw_mbs_02.py` - Fixed bitmask definitions
- `api/modbus/__init__.py` - Uses masks via `has_circuit()` method
- `entities/control_unit/selects.py` - Operation mode select conditions
- `entities/circuit/climate.py` - Climate entity HVAC modes
- `entities/thermal/sensors.py` - Cooling thermal sensors

## Timeline

- **2025-11-09**: First report (beta.3) by @tijmenvanstraten
- **2026-01-08**: Follow-up report (beta.5)
- **2026-02-03**: Root cause identified and fixed

## Lessons Learned

1. When refactoring constants into new structures, verify bit positions against documentation
2. User feedback about "partial working" (state reading OK, capability detection broken) was key to narrowing down the issue
3. Modbus dumps are invaluable for debugging register interpretation issues
