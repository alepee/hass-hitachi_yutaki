# Investigation: Thermal energy misclassification during DHW/Pool cycles

## Context

When the heat pump switches from cooling circuits to DHW (or pool), the water temperature sensors briefly reflect circuit temperatures, producing a negative ΔT. The thermal energy accumulator classifies energy based on ΔT sign, so this transient negative delta is incorrectly counted as cooling energy.

A fix was implemented (uncommitted) to propagate `operation_mode` through the thermal service chain, forcing DHW/pool energy to heating regardless of ΔT.

This investigation audits the full operation mode handling across the codebase to assess duplication, consistency, robustness, and architectural alignment.

## Data flow

```
Modbus register 1090 (raw int: 0-11)
       │
       ▼
OPERATION_STATE_MAP                          ← api/modbus/registers/
       │  { 8: "dhw_on", 6: "heat_thermo_on", ... }
       ▼
deserialize_operation_state()                ← api/modbus/registers/
       │  "dhw_on" → "operation_state_dhw_on"
       ▼
coordinator.data["operation_state"]
       │
       ▼
_OPERATION_STATE_TO_MODE                     ← entities/base/sensor.py:59-65
       │  "operation_state_dhw_on" → "dhw"
       ▼
       ├──→ COPInput.operation_state ──→ COPService._is_mode_matching()
       │         filtering: skip measurement if mode ≠ expected
       │
       └──→ ThermalPowerService.update(operation_mode=)
                    │
                    ▼
             ThermalEnergyAccumulator.update(operation_mode=)
                    reclassification: force DHW/pool → heating
```

## Findings

### 1. Duplication — OPERATION_STATE_MAP

`OPERATION_STATE_MAP` and `deserialize_operation_state()` are **identical** in both gateway files:

| File | Lines |
|------|-------|
| `api/modbus/registers/atw_mbs_02.py` | 51-64, 130-134 |
| `api/modbus/registers/hc_a_mb.py` | 70-83, 138-142 |

**Severity: moderate.** Both gateways have the same 12 operation states and the same deserialization function. If a state is added or renamed, both files must be updated in sync.

**Mitigating factor:** Gateway register maps are intentionally independent (separate classes, different addresses). Extracting the shared map would break that autonomy. Acceptable trade-off as long as both gateways share the same operation state protocol.

### 2. Architecture — mapping in the entity layer

`_OPERATION_STATE_TO_MODE` lives in `entities/base/sensor.py:59-65`. This dictionary translates Modbus-level keys (`"operation_state_dhw_on"`) into domain concepts (`"dhw"`).

This is an **adapter responsibility**, not an entity one. The `entities/base/sensor.py` file currently handles:
- Modbus → domain translation (adapter concern)
- Service instantiation and wiring (composition root concern)
- Coordinator state reads (adapter concern)
- HA entity rendering (entity concern)

The mapping is consumed in **two places** within the same file:
- `_get_cop_input()` (~line 295) for COP
- `_update_thermal_energy()` (~line 571) for thermal

**Risk:** If a third consumer needs the mode (e.g. a diagnostic sensor, an automation trigger), it must either import from `entities/base/sensor.py` (entity→entity coupling) or re-duplicate the mapping.

### 3. Naming inconsistency

| Layer | Field | Values | Actual semantics |
|-------|-------|--------|------------------|
| `COPInput` | `operation_state` | `"heating"`, `"dhw"`, ... | **mode** (domain) |
| `COPService` | `expected_mode` | `"heating"`, `"dhw"`, ... | mode |
| `ThermalPowerService` | `operation_mode` | `"heating"`, `"dhw"`, ... | mode |
| `ThermalEnergyAccumulator` | `operation_mode` | `"heating"`, `"dhw"`, ... | mode |
| `coordinator.data` | `"operation_state"` | `"operation_state_dhw_on"` | state (deserialized) |
| `coordinator.data` | `"operation_state_code"` | `8` | state (raw) |

`COPInput.operation_state` is named "state" but carries a **domain mode** (`"dhw"`), not the Modbus state (`"operation_state_dhw_on"`). This is misleading — one could reasonably pass the raw coordinator value, which would silently break mode matching.

The thermal chain uses `operation_mode` consistently, which is the correct name.

### 4. COP vs Thermal — asymmetric strategies

Both services consume the same mode but handle it differently:

| Aspect | COP | Thermal |
|--------|-----|---------|
| Strategy | **Filter**: skip measurement if mode ≠ expected | **Reclassify**: force DHW/pool energy to heating |
| Location | `COPService._is_mode_matching()` | `ThermalEnergyAccumulator.update()` |
| Input | `COPInput.operation_state` (dataclass field) | `operation_mode` (function parameter) |

Both approaches are valid for their respective use cases, but they rely on the same upstream mapping without formalizing it as a shared domain concept.

### 5. Robustness

**Good:**
- `operation_mode=None` preserves existing ΔT-based behavior (backward compatible)
- Only active states (`*_on`) are mapped; transitional states (`demand_off`, `thermo_off`) return `None` — correct behavior
- COP rejects measurements when `operation_state is None` (no false positives)
- 6 tests covering nominal and edge cases

**Fragile:**
- The mapping relies on **deserialized string format** (`"operation_state_dhw_on"`). If `deserialize_operation_state()` changes its prefix convention, `_OPERATION_STATE_TO_MODE.get()` silently returns `None` — no error raised
- Mode values (`"heating"`, `"dhw"`, `"pool"`, `"cooling"`) are **bare string literals** across the domain layer, COP models, thermal accumulator, entity mapping, and tests. A typo would go undetected
- `ThermalEnergyAccumulator` hardcodes `if operation_mode in ("dhw", "pool")` — any new mode requiring the same treatment must be added here manually

### 6. Readability

`entities/base/sensor.py` is a **~680-line god object** concentrating too many responsibilities: operation mode mapping, service wiring, Recorder rehydration, COP logic, thermal logic, and HA entity rendering. It is the most fragile file in the project.

The thermal `operation_mode` flow is straightforward (explicit parameter passed down). The COP flow is less transparent because `COPInput.operation_state` is populated with a pre-transformed value from the entity layer.

## Summary

| Axis | Verdict | Detail |
|------|---------|--------|
| **Duplication** | Acceptable | `OPERATION_STATE_MAP` duplicated between gateways — reasonable trade-off |
| **Architecture** | **Needs improvement** | Modbus→domain mapping should be an adapter, not in entity layer |
| **Naming** | **Inconsistent** | `COPInput.operation_state` carries a mode, not a state |
| **Robustness** | Correct | Backward-compatible, but fragile on string literals |
| **Readability** | Moderate | `sensor.py` overloaded, but the flow is traceable |
| **Tests** | Good | 6 tests covering nominal cases, edge cases, and backward compat |
| **Overall approach** | **Sound** | Fixes a real bug with minimal blast radius |

## Recommendations

If a refactor is undertaken, the following changes would strengthen the architecture:

### R1. Extract mode mapping to a dedicated adapter ✅

Create `adapters/providers/operation_mode.py` with a function that takes a coordinator data dict and returns the domain mode. This moves the Modbus→domain translation out of the entity layer.

**Implémenté** : `adapters/providers/operation_mode.py` créé avec `resolve_operation_mode()` et `get_accepted_operation_states()`. Le mapping `_OPERATION_STATE_TO_MODE` a été supprimé de `entities/base/sensor.py`.

### R2. Define mode constants in the domain layer ✅

Create constants in `domain/models/` (e.g. `MODE_HEATING = "heating"`, `MODE_DHW = "dhw"`, etc.) and use them everywhere instead of string literals. This makes typos impossible and provides a single reference for valid modes.

**Implémenté** : `domain/models/operation.py` créé avec `MODE_HEATING`, `MODE_COOLING`, `MODE_DHW`, `MODE_POOL` et `HEATING_ONLY_MODES`. Tous les string literals remplacés dans le code source et les tests.

### R3. Rename `COPInput.operation_state` to `operation_mode` ✅

Align with the thermal service naming. Both fields carry the same domain-level concept.

**Implémenté** : Champ renommé dans `COPInput`, `COPService._is_mode_matching()`, `entities/base/sensor.py` et tous les tests.

### R4. Consider factoring OPERATION_STATE_MAP

If both gateways are confirmed to always share the same operation state protocol, extract the map to a shared module (e.g. `api/modbus/registers/common.py`). Keep gateway-specific register definitions separate.

### R5. Reduce sensor.py responsibilities

Long-term, split `entities/base/sensor.py` into focused modules:
- Service wiring / composition
- COP entity behavior
- Thermal entity behavior
- Base sensor rendering
