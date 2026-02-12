# Investigation: COP DHW always identical to COP Heating (#191)

Reported by @tijmenvanstraten in [discussion #117](https://github.com/alepee/hass-hitachi_yutaki/discussions/117#discussioncomment-15720414).

## Symptom

Since the v2.0.0 betas, the COP DHW and COP Heating sensors always display the same value. In v1.9.x they were distinct.

## Data Flow Analysis

```
Modbus registers
  → Coordinator (reads operation_state, water temps, compressor freq, etc.)
    → Entity layer (entities/base/sensor.py)
      └── _get_cop_input()  → COPService.update()
                                ├── _is_compressor_running()
                                ├── _is_mode_matching()    ← filtering happens here
                                └── accumulator.add_measurement()
```

### How v1.9 filtered by mode

In v1.9, `_get_cop_value()` (sensor.py:1284-1298) used the **`operation_state`** register (Modbus 1090) to gate accumulation per COP type:

```python
cop_state_map = {
    "cop_heating": 6,   # heat_thermo_on
    "cop_cooling": 3,   # cool_thermo_on
    "cop_dhw":     8,   # dhw_on
    "cop_pool":    10,  # pool_on
}
expected_state = cop_state_map.get(self.entity_description.key)
if operation_state != expected_state:
    return None  # skip — don't accumulate
```

Each COP sensor only accumulated measurements during **its own operational mode**. The heat pump cycles between heating, DHW, defrost, etc., and `operation_state` precisely reflects which mode is active at any given moment.

### How v2.0 filters by mode (broken)

The hexagonal refactoring replaced `operation_state` filtering with `hvac_action` filtering in `COPService._is_mode_matching()` (cop.py:249-268):

```python
def _is_mode_matching(self, data: COPInput) -> bool:
    # DHW and Pool modes don't need HVAC action filtering
    if self._expected_mode in ("dhw", "pool", None):
        return True  # ← ALWAYS True for DHW and Pool

    if data.hvac_action is None:
        return False

    return data.hvac_action == self._expected_mode
```

And `hvac_action` is derived from `unit_mode` (register 1001 = heat/cool/auto) — **not** from `operation_state` (register 1090).

### COP calculator mapping

From `entities/base/sensor.py:213-220`:

```python
cop_calculators = {
    "cop_heating": (thermal_power_calculator_heating_wrapper, "heating"),
    "cop_cooling": (thermal_power_calculator_cooling_wrapper, "cooling"),
    "cop_dhw":     (thermal_power_calculator_heating_wrapper, "dhw"),
    "cop_pool":    (thermal_power_calculator_heating_wrapper, "pool"),
}
```

Both `cop_heating` and `cop_dhw` use the **same thermal calculator** (`thermal_power_calculator_heating_wrapper`).

## Root Cause

Two combined issues cause identical values:

1. **No mode filtering for DHW**: `_is_mode_matching()` returns `True` unconditionally when `expected_mode == "dhw"`, so COP DHW accumulates during **every** compressor cycle (heating, DHW, defrost recovery…)

2. **Same thermal calculator**: Both COP Heating and COP DHW use `thermal_power_calculator_heating_wrapper` (positive when outlet > inlet), and receive identical sensor data (same water inlet/outlet/flow, same compressor current)

Since the heat pump spends the majority of its time in heating mode, both accumulators end up with essentially the same measurement set → identical COP.

### Comparison table

| Aspect | v1.9 | v2.0 |
|--------|------|------|
| **DHW filter** | `operation_state == 8` (dhw_on) | none (`_is_mode_matching → True`) |
| **Heating filter** | `operation_state == 6` (heat_thermo_on) | `hvac_action == "heating"` |
| **Cooling filter** | `operation_state == 3` (cool_thermo_on) | `hvac_action == "cooling"` |
| **Pool filter** | `operation_state == 10` (pool_on) | none (`_is_mode_matching → True`) |
| **Data source** | `operation_state` register 1090 | `unit_mode` register 1001 |

## Operation State Register (1090)

The `operation_state` register provides fine-grained mode information:

```python
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
```

This is already read and deserialized into string values like `"operation_state_dhw_on"` (see `atw_mbs_02.py:134-138`).

## Proposed Solution

Reintroduce `operation_state` filtering in the COP pipeline, respecting the hexagonal architecture.

### 1. Extend `COPInput` model

Add an `operation_state` field to the domain model (`domain/models/cop.py`):

```python
@dataclass
class COPInput:
    # ... existing fields ...
    hvac_action: str | None = None
    operation_state: str | None = None  # e.g. "heating", "cooling", "dhw", "pool"
```

Use **domain-level values** (not raw Modbus strings) to keep the domain layer infrastructure-agnostic.

### 2. Map operation_state in entity layer

In `_get_cop_input()` (`entities/base/sensor.py`), map the deserialized register value to a domain concept:

```python
OPERATION_STATE_TO_MODE = {
    "operation_state_heat_thermo_on": "heating",
    "operation_state_cool_thermo_on": "cooling",
    "operation_state_dhw_on": "dhw",
    "operation_state_pool_on": "pool",
}

operation_state_raw = self.coordinator.data.get("operation_state")
operation_mode = OPERATION_STATE_TO_MODE.get(operation_state_raw)
```

### 3. Fix `_is_mode_matching` in COP service

Replace the current logic (`domain/services/cop.py`) to filter **all** modes by `operation_state`:

```python
def _is_mode_matching(self, data: COPInput) -> bool:
    if self._expected_mode is None:
        return True
    if data.operation_state is None:
        return False
    return data.operation_state == self._expected_mode
```

This way:
- `cop_heating` accumulates only when `operation_state == "heating"` (was: heat_thermo_on)
- `cop_dhw` accumulates only when `operation_state == "dhw"` (was: dhw_on)
- `cop_cooling` accumulates only when `operation_state == "cooling"` (was: cool_thermo_on)
- `cop_pool` accumulates only when `operation_state == "pool"` (was: pool_on)

### 4. Simplify: `hvac_action` becomes redundant for COP

The `hvac_action` field (derived from `unit_mode`) was a lossy replacement for `operation_state`. With `operation_state` restored, `hvac_action` is no longer needed for COP filtering. It can be kept for other uses (thermal energy mode detection) but the COP service should rely on `operation_state`.

### Affected files

| File | Change |
|------|--------|
| `domain/models/cop.py` | Add `operation_state` field to `COPInput` |
| `domain/services/cop.py` | Rewrite `_is_mode_matching` to use `operation_state` |
| `entities/base/sensor.py` | Map register value in `_get_cop_input()`, pass to `COPInput` |

No changes to thermal calculators, adapters, or entity descriptions.

### Interaction with DefrostGuard (#190)

The DefrostGuard (introduced in `06e6f4f`) gates data flow upstream of COP. During defrost/recovery, `_get_cop_input()` already returns `None` so no data reaches the COP service. The `operation_state` fix is complementary: DefrostGuard handles defrost interference, `operation_state` filtering handles mode separation.

## Open Questions

- Should `hvac_action` be removed from `COPInput` entirely, or kept for backward compatibility?
- The `_detect_mode_from_temperatures()` fallback (AUTO mode) — is it still useful for COP now that `operation_state` provides exact mode? It may still be relevant for thermal energy tracking.

## Future Idea: DHW Tank Energy Estimation

> Not related to the bug — just a feature idea raised during the discussion.

@tijmenvanstraten asked whether it would be possible to estimate the energy stored in the DHW water tank using `Q = m × c × ΔT`. Note: this has no impact on COP calculation (which correctly measures heat pump efficiency at its hydraulic boundaries, regardless of what's downstream).

**Available data:**
- `dhw_current_temp` (register 1080) — single tank temperature sensor

**Missing data:**
- Cold water inlet temperature (no Modbus register available)
- Tank volume (not known by the heat pump, would require user configuration)

**Limitations:**
- A single temperature sensor does not account for tank stratification (hot at top, cold at bottom), so any estimate would be approximate
- Would need user-provided config values (tank volume, assumed cold water temperature)

Low priority — to revisit later if there's interest.
