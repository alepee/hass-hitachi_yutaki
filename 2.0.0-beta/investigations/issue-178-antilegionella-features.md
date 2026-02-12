# Issue #178: Anti-legionella Features Not Working

**Status**: 📋 Ready for Implementation
**Priority**: 🟡 Medium
**Reporter**: tijmenvanstraten
**Model**: Yutaki S Combi
**First reported**: 2025-11-09 (beta.3)

---

## Executive Summary

Multiple anti-legionella features are not working properly in v2.0.0 beta. Three issues were reported: temperature setting reverts, 60°C minimum validation, and cycle trigger button not working.

**Root cause identified**: The code reads anti-legionella status from CONTROL registers (1030/1031) instead of dedicated STATUS registers (1084/1085). Control registers are write-command registers that may not reflect actual state after processing. This causes the UI to show stale/incorrect values, making it appear that writes "don't work" when the heat pump may have actually processed the command.

**Secondary finding**: The ATW-MBS-02 documentation note (*9) indicates anti-legionella control can only be used "if the function is enabled on the LCD". If the anti-legionella function is not activated on the heat pump's control panel, Modbus writes are silently ignored.

---

## Problem Statement

### 1. Cannot modify anti-legionella temperature
- **Symptom**: Value reverts to previous setting after submission
- **Register**: 1031 (`dhw_antilegionella_temp`) — CONTROL register
- **Current implementation**: Writes `int(temperature)` directly
- **Root cause**: Read-back uses address 1031 (control) instead of 1085 (status)

### 2. Temperature validation: 60°C minimum enforced
- **Symptom**: Error when setting temperature below 60°C
- **Source**: Integration code (`entities/dhw/numbers.py:39-40`)
- **Current limits**: `native_min_value=60, native_max_value=80`
- **Finding**: ATW-MBS-02 doc says 0~80°C with note (*3) "limited by the machine according to its rank"

### 3. Start anti-legionella cycle button not working
- **Symptom**: Button can be pressed, but cycle doesn't start
- **Register**: 1030 (`dhw_antilegionella`) — CONTROL register
- **Current implementation**: Writes `1` to trigger
- **Root cause**: Status binary sensor reads address 1030 (control) instead of 1084 (status)

---

## ATW-MBS-02 Documentation Analysis

### Section 5.3 — Line-up Yutaki 2016 Series

#### Control Registers (R/W) — for WRITING commands

| Register | Address | Description | Range | Type |
|----------|---------|-------------|-------|------|
| 1025 | 1024 | Control DHWT Run/Stop | 0: Stop, 1: Run | R/W |
| 1026 | 1025 | Control DHWT Setting Temperature | 0~80 °C(*3) | R/W |
| 1027 | 1026 | Control DHW Boost | 0: No request, 1: Request | R/W |
| 1028 | 1027 | Control DHW Demand Mode | 0: Standard, 1: High demand | R/W |
| 1029 | 1028 | Control Swimming Pool Run/Stop | 0: Stop, 1: Run | R/W |
| 1030 | 1029 | Control Swimming Pool Setting Temperature | 0~80 °C(*3) | R/W |
| **1031** | **1030** | **Control Anti Legionella Run (*9)** | **0: Stop, 1: Run** | **R/W** |
| **1032** | **1031** | **Control Anti Legionella Setting Temperature** | **0~80 °C(*3)** | **R/W** |

#### Status Registers (R) — for READING actual state

| Register | Address | Description | Range | Type |
|----------|---------|-------------|-------|------|
| 1077 | 1076 | Status DHWT Run/Stop | 0: Stop, 1: Run | R |
| 1078 | 1077 | Status DHWT Setting Temperature | 0~80 °C | R |
| 1079 | 1078 | Status DHW Boost | 0: Stop, 1: Run | R |
| 1081 | 1080 | Status DHWT Temperature | -80~100 °C(*1) | R |
| **1085** | **1084** | **Status Anti Legionella Run** | **0: Stop, 1: Run** | **R** |
| **1086** | **1085** | **Status Anti Legionella Setting Temperature** | **0~80 °C(*1)** | **R** |

#### Relevant Footnotes (page 16)

- **(*1)**: Signed 16-bit value using 2-complement format for negative values
- **(*3)**: "This value is limited by the machine according to its rank"
- **(*9)**: "This parameter can only be used if the function is enabled on the LCD." *(applies to anti-legionella run register)*

---

## Root Cause Analysis

### Primary: Wrong registers for reading status

The code defines:
```python
REGISTER_DHW = {
    "dhw_antilegionella": RegisterDefinition(1030),       # Control (write) ✅
    "dhw_antilegionella_temp": RegisterDefinition(1031),   # Control (write) ✅
    "dhw_antilegionella_status": RegisterDefinition(1030), # ← WRONG! Should be 1084
    "dhw_current_temp": RegisterDefinition(1080, ...),     # Status (read) ✅ correct pattern
}
```

The `dhw_current_temp` register correctly uses the STATUS address (1080), but `dhw_antilegionella_status` incorrectly reuses the CONTROL address (1030). There is no entry for reading the actual anti-legionella temperature setting back from the heat pump (STATUS register 1085).

Both CONTROL and STATUS registers are readable (R/W vs R), but they serve different purposes:
- **CONTROL** (1030/1031): reflects the last command sent
- **STATUS** (1084/1085): reflects the actual heat pump state

**Impact**:
- Temperature entity reads `dhw_antilegionella_temp` (address 1031, control) → shows the last command value, not necessarily the actual stored value
- Binary sensor reads `dhw_antilegionella_status` (address 1030, control) → shows the last command, not the actual cycle state
- User sees: "value reverts" and "button doesn't work" because UI reads command registers instead of actual state

**Evidence**: The pattern of separating CONTROL and STATUS registers is already used correctly for `dhw_current_temp` which reads from STATUS register 1080, not from the control register 1025.

### Secondary: Prerequisite restriction (footnote *9)

The ATW-MBS-02 documentation marks the anti-legionella run register with note (*9):
> "This parameter can only be used if the function is enabled on the LCD."

This means the anti-legionella function must be **activated on the heat pump's LCD/control panel** before it can be controlled via Modbus. If the function is not enabled on the LCD, writes to register 1030 are **silently ignored** by the gateway. This is a hardware-level prerequisite that the integration cannot bypass.

### Tertiary: No error feedback

Both button and number entities ignore the return value of write operations:

```python
# entities/base/button.py:63-67
async def async_press(self) -> None:
    if self.entity_description.action_fn:
        await self.entity_description.action_fn(self.coordinator)  # Return value ignored
        await self.coordinator.async_request_refresh()

# entities/base/number.py:132-138
async def async_set_native_value(self, value: float) -> None:
    if self.entity_description.set_fn:
        await self.entity_description.set_fn(...)  # Return value ignored
        await self.coordinator.async_request_refresh()
```

---

## Hypothesis Validation

| Hypothesis | Status | Finding |
|------------|--------|---------|
| H1: Register requires different encoding | ❌ Eliminated | Doc confirms 0~80°C whole degrees and 0/1 for run. Code is correct. |
| H2: Prerequisites not met | ⚠️ Possible | Footnote (*9): function must be enabled on LCD. Needs user verification. |
| H3: Register 1030 read/write behavior | ✅ **Confirmed** | Control register is one-shot trigger. Status must be read from 1084. |
| H4: Temperature must be set before cycle | ❓ Unknown | Cannot determine without testing. |
| **H5: Wrong STATUS registers** | ✅ **Root cause** | Code reads control registers (1030/1031) instead of status registers (1084/1085). |

---

## Git History Analysis

Key commits in anti-legionella evolution:

1. **Initial commit** (`9841d3d`): Anti-legionella as on/off switch at register 1030, temp range 0-80°C
2. **Rename fix** (`bc7d4b0`): Added `dhw_` prefix, changed min temp from 0 to 60°C
3. **Button refactor** (`6625bb2`, v1.8.1): Changed from switch to button trigger, added binary sensor
4. **Encoding revert** (`f653d74`): Removed `convert_from_tenths` — confirmed whole degrees, not tenths
5. **v2.0.0-beta**: Ported to hexagonal architecture, same register addresses preserved

**No evidence of successful user confirmation** — the anti-legionella features may have never worked correctly since v1.8.1 (when they changed from toggle switch to one-shot button).

---

## Implementation Plan

### Fix 1: Add proper STATUS registers (HIGH priority)

```python
# api/modbus/registers/atw_mbs_02.py — REGISTER_DHW
REGISTER_DHW = {
    # Control registers (for writing)
    "dhw_power": RegisterDefinition(1024),
    "dhw_target_temp": RegisterDefinition(1025),
    "dhw_boost": RegisterDefinition(1026),
    "dhw_high_demand": RegisterDefinition(1027),
    "dhw_antilegionella": RegisterDefinition(1030),
    "dhw_antilegionella_temp": RegisterDefinition(1031),
    # Status registers (for reading)
    "dhw_current_temp": RegisterDefinition(1080, deserializer=convert_signed_16bit),
    "dhw_antilegionella_status": RegisterDefinition(1084),         # ← FIX: was 1030
    "dhw_antilegionella_temp_status": RegisterDefinition(1085),    # ← NEW: read actual temp
}
```

### Fix 2: Update API to read from status registers

```python
# api/modbus/__init__.py
def get_dhw_antilegionella_temperature(self) -> float | None:
    """Get anti-legionella target temperature from STATUS register."""
    temp = self._data.get("dhw_antilegionella_temp_status")  # ← Read from status
    if temp is None:
        return None
    return float(temp)

@property
def is_antilegionella_active(self) -> bool:
    """Return True if anti-legionella cycle is running."""
    status = self._data.get("dhw_antilegionella_status")  # Now reads from 1084
    return status == 1
```

### Fix 3: Add debug logging for writes

```python
# api/modbus/__init__.py
async def start_dhw_antilegionella(self) -> bool:
    """Start anti-legionella treatment cycle."""
    _LOGGER.debug("Starting anti-legionella cycle (writing 1 to register 1030)")
    result = await self.write_value("dhw_antilegionella", 1)
    _LOGGER.debug("Anti-legionella start result: %s", result)
    return result

async def set_dhw_antilegionella_temperature(self, temperature: float) -> bool:
    """Set anti-legionella target temperature (stored in °C)."""
    _LOGGER.debug("Setting anti-legionella temp to %s°C (register 1031)", temperature)
    result = await self.write_value("dhw_antilegionella_temp", int(temperature))
    _LOGGER.debug("Anti-legionella temp set result: %s", result)
    return result
```

### Fix 4: Adjust temperature validation (LOW priority)

Two options:
- **Keep 60°C minimum**: 60°C is the standard for effective legionella prevention. Document why.
- **Lower to heat pump limits**: Doc says 0~80°C, machine limits by rank. Consider 55°C as compromise (still effective, more models supported).

### Fix 5: Enable number entity by default

```python
# entities/dhw/numbers.py
entity_registry_enabled_default=True,  # Was False — users couldn't find it
```

---

## Testing Strategy

### Automated Tests
- Unit test: verify STATUS register addresses (1084, 1085) are in REGISTER_DHW
- Unit test: verify `get_dhw_antilegionella_temperature()` reads from status key
- Unit test: verify `is_antilegionella_active` reads from status register

### User Testing (with reporter)
1. Deploy fix with debug logging enabled
2. Ask user to:
   a. Set anti-legionella temperature → verify value persists in UI
   b. Press anti-legionella button → verify binary sensor shows "running"
   c. Check HA logs for debug output confirming write success
3. If writes still fail, investigate footnote (*9) — check if function is enabled on LCD

### Verification Questions for Reporter
- Is the anti-legionella function enabled on the heat pump's LCD? (footnote *9 requirement)
- Does the anti-legionella cycle work from the heat pump's own controls/LCD?
- What is the current anti-legionella temperature shown on the LCD?

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| New STATUS registers not polled | Medium | Verify coordinator reads all REGISTER_DHW keys |
| Register 1084/1085 not available on all models | Medium | Add debug logging, test on reporter's model |
| Footnote (*9): function not enabled on LCD | High | Document requirement, add user-facing warning/diagnostic |
| Breaking existing binary sensor | Low | Same key name, just different address |

---

## Related Code Paths

```
entities/dhw/numbers.py              → anti-legionella temp entity
entities/dhw/buttons.py              → anti-legionella trigger button
entities/dhw/binary_sensors.py       → anti-legionella status sensor
entities/base/number.py              → _create_numbers(), validation
entities/base/button.py              → _create_buttons(), action handling
api/modbus/__init__.py               → write_value(), get/set methods, is_antilegionella_active
api/modbus/registers/atw_mbs_02.py   → RegisterDefinition for 1030, 1031, 1084, 1085
```

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-05 | Created investigation | Consolidated from issues #168, #172, #174 |
| 2026-02-05 | Root cause: wrong STATUS registers | ATW-MBS-02 doc confirms separate CONTROL (1030/1031) and STATUS (1084/1085) registers |
| 2026-02-05 | Keep 60°C minimum for now | Standard for legionella prevention, can revisit later |
| 2026-02-05 | Corrected footnote: (*9) not (*8) | Anti-legionella requires function enabled on LCD, not Modbus thermostat |

---

## References

- GitHub Issue: [#178](https://github.com/alepee/hass-hitachi_yutaki/issues/178)
- Related closed issues: #168, #172, #174 (consolidated into #178)
- Beta testing discussion: [#117](https://github.com/alepee/hass-hitachi_yutaki/discussions/117)
- ATW-MBS-02 documentation: `documentation/gateway/ATW-MBS-02.pdf` — pages 14-16 (Section 5.3)

---

*Created: 2026-02-05*
*Updated: 2026-02-05 — Root cause identified, ready for implementation*
