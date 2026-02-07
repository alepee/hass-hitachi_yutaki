# Investigation: COP cooling calculated during heating mode (#190)

Reported by @tijmenvanstraten in [discussion #117](https://github.com/alepee/hass-hitachi_yutaki/discussions/117#discussioncomment-15716385).

## Symptom

COP calculations are made for cooling even though the heat pump is set to heating.

## Data Flow Analysis

```
Modbus registers
  → Coordinator (reads is_defrosting, water temps, compressor freq, etc.)
    → Entity layer (entities/base/sensor.py)
      ├── _get_cop_input()  → COPService.update()
      └── _update_thermal_energy() → ThermalService.update()
```

### COP path

`_get_cop_input()` builds a `COPInput` and calls `COPService.update()`.
The HVAC action is determined by `_get_hvac_action()`:

- **HEAT/COOL mode**: returns `"heating"` / `"cooling"` directly from register 1001
- **AUTO mode**: calls `_detect_mode_from_temperatures()` which infers mode from ΔT sign (outlet − inlet)

The `COPService` filters measurements by expected mode (`_is_mode_matching`): a COP cooling sensor only accepts `hvac_action == "cooling"`.

**Problem**: `COPInput` has no `is_defrosting` field. The COP service has zero defrost awareness.

### Thermal path

`_update_thermal_energy()` passes `is_defrosting=self.coordinator.api_client.is_defrosting` to the thermal service, which zeros power during defrost. However, the **post-defrost recovery phase** is not filtered — only the exact defrost window is.

## Root Cause

During a defrost cycle in AUTO mode:

1. The heat pump reverses its cycle to melt ice on the outdoor coil
2. Water outlet temperature drops below inlet (ΔT reverses)
3. `_detect_mode_from_temperatures()` returns `"cooling"` (ΔT < −0.5)
4. COP cooling service: `expected_mode == "cooling"`, `hvac_action == "cooling"` → match
5. `thermal_power_calculator_cooling_wrapper` produces positive power (outlet < inlet)
6. Compressor IS running during defrost → electrical power > 0
7. Both powers > 0 → measurement is stored in the COP cooling accumulator
8. After several defrost cycles → false COP cooling values appear

Even in explicit HEAT mode (not AUTO), the **post-defrost recovery** produces abnormal ΔT that pollutes COP heating measurements (thermal power is low during recovery, skewing the ratio).

## Current Defrost Filtering

| Layer | Defrost filtered | Recovery filtered |
|-------|:---:|:---:|
| COP service | ❌ | ❌ |
| Thermal accumulator | ✅ (zeros power) | ❌ |

The thermal accumulator's `update()` method handles defrost:
```python
if is_defrosting:
    self._update_energy(0.0, mode=self._last_mode)  # keep clock, zero power
    return
```

The COP service has no equivalent.

## Proposed Solution: Upstream Data Quality Gate

Rather than adding defrost filtering to each domain service, implement a **centralized defrost+recovery state machine** in the entity layer.

### State Machine

```
         is_defrosting=True           is_defrosting=False
NORMAL ──────────────────► DEFROST ──────────────────► RECOVERY
  ▲                                                       │
  │         ΔT sign consistent for N readings             │
  │              OR safety timeout elapsed                │
  └───────────────────────────────────────────────────────┘
```

Three states:
- **NORMAL**: data flows to services normally
- **DEFROST**: `is_defrosting == True`, data is unreliable
- **RECOVERY**: defrost ended, waiting for ΔT stabilization

### Stabilization Criteria

Exit RECOVERY → NORMAL when:
- The ΔT sign is **consistent with the current operating mode** for N consecutive readings
  - Heating mode: `outlet > inlet` (ΔT > +threshold)
  - Cooling mode: `outlet < inlet` (ΔT < −threshold)
- OR a **safety timeout** has elapsed (prevents stuck state)

### Per-Service Behavior When State ≠ NORMAL

| Service | Behavior |
|---------|----------|
| **COP** | `_get_cop_input()` returns `None` → service not called |
| **Thermal** | `_update_thermal_energy()` passes zeroed powers → accumulator keeps its clock advancing |

### Simplification

With this upstream gate:
- **Remove `is_defrosting`** from `ThermalEnergyAccumulator.update()` — the entity layer handles it
- **No changes** to `COPInput` or `COPService` — they never see defrost data
- The thermal accumulator's **post-cycle lock** (compressor stop inertia) remains untouched — it handles a different concern

### Affected Files

| File | Change |
|------|--------|
| `entities/base/sensor.py` | Add defrost state machine, gate COP and thermal updates |
| `domain/services/thermal/accumulator.py` | Remove `is_defrosting` parameter and handling |
| `domain/services/thermal/service.py` | Remove `is_defrosting` passthrough |

No changes to domain models or COP service.

## Open Questions

- **N consecutive readings**: how many readings before considering ΔT stable? (suggest 3, at ~30s polling = ~90s)
- **Safety timeout**: max duration for RECOVERY state? (suggest 5 minutes)
- **Threshold**: reuse the existing ±0.5°C from `_detect_mode_from_temperatures()`?
