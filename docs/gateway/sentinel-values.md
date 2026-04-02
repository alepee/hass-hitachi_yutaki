# Gateway Data Filtering

The gateway layer is responsible for ensuring that only meaningful data reaches upstream consumers (coordinator, entities, telemetry). Two mechanisms work together to achieve this.

## 1. Sentinel Value Filtering

Gateway devices return sentinel values when a sensor is physically unavailable. These are Modbus protocol conventions — the gateway filters them in `_read_register()` using `RegisterDefinition.sentinel_values` and returns `None` instead.

### Known Sentinels

| Value | Meaning | Registers | Notes |
|-------|---------|-----------|-------|
| **-127** | Sensor not installed | `water_outlet_2_temp`, `water_outlet_3_temp`, `pool_current_temp` | Hardware absent |
| **-67** | Module not available | `dhw_current_temp` | Optional module not installed |

Values are checked **after** deserialization (i.e. after `convert_signed_16bit` converts unsigned 16-bit to signed).

### Implementation

Each `RegisterDefinition` declares its sentinel values:

```python
RegisterDefinition(
    1204, deserializer=convert_signed_16bit, sentinel_values=frozenset({-127})
)
```

In `_read_register()`, after deserialization:

```python
if value is not None and definition.sentinel_values and value in definition.sentinel_values:
    return None
```

### By Profile

#### yutaki_s80 (Dual Compressor)

| Register | Sentinel | Reason |
|----------|----------|--------|
| `dhw_current_temp` | -67 | S80 does not support DHW |
| `water_outlet_2_temp` | -127 | No circuit 2 outlet sensor |
| `water_outlet_3_temp` | -127 | No circuit 3 outlet sensor |
| `pool_current_temp` | -127 | No pool module |

#### yutaki_s / yutaki_s_combi

| Register | Sentinel | Notes |
|----------|----------|-------|
| `water_outlet_2_temp` | -127 | Variable — depends on installation |
| `water_outlet_3_temp` | -127 | Variable — depends on installation |
| `pool_current_temp` | -127 | When pool not installed |

## 2. Module Gating (`system_config`)

Even after sentinel filtering, the gateway still reads registers for unconfigured modules. These return default values (e.g. `dhw_target_temp: 45`, `pool_target_temp: 24`) that are technically valid but represent non-existent hardware.

The `_gate_unconfigured_modules()` method purges data for modules not declared in the `system_config` register after each read cycle.

### Gated Modules

| Module | Condition | Keys removed |
|--------|-----------|-------------|
| DHW | `system_config & mask_dhw == 0` | All `dhw_*` keys |
| Pool | `system_config & mask_pool == 0` | All `pool_*` keys |
| Circuit 2 | No heating AND no cooling configured | All `circuit2_*` keys |

### What is NOT gated here

| Module | Condition source | Why not in gateway |
|--------|-----------------|-------------------|
| Secondary compressor | `profile.supports_secondary_compressor` | Model-specific (S80 only), determined by profile detection, not `system_config` |
| Boiler | `profile.supports_boiler` | Same — profile-level capability |

These are handled by entity-level `condition` callbacks, which check the profile.

## Relationship with Entity Conditions

Entities also check `has_dhw()`, `has_pool()`, etc. to decide whether to create themselves. This is **not duplication** — the two mechanisms serve different purposes:

| | Gateway gating | Entity condition |
|---|---|---|
| **Purpose** | Data quality — don't propagate noise | UI — should this entity exist? |
| **Based on** | `system_config` register | `has_dhw()`, `profile.*` |
| **Affects** | `self._data` (all consumers) | Entity creation only |
| **Example** | Purge `dhw_target_temp: 45` phantom | Don't create DHW power switch |

A temporary Modbus read error returns `None` for one cycle but does not remove the entity. The gateway gate is based on `system_config` which is stable across reads.

## Data Flow

```
Modbus registers
    │
    ▼
_read_register()
    ├── 0xFFFF (sensor error) → None          [existing]
    ├── sentinel (-127, -67)  → None          [sentinel filtering]
    └── valid value           → deserialized
    │
    ▼
_gate_unconfigured_modules()
    ├── DHW not in system_config  → dhw_* removed
    ├── Pool not in system_config → pool_* removed
    └── Circuit 2 not configured  → circuit2_* removed
    │
    ▼
self._data (clean)
    │
    ├──→ Coordinator → Entities (check has_dhw() for creation)
    └──→ Coordinator → Telemetry collector (only real data)
```

## References

- Modbus ATW-MBS-02 datasheet: `docs/gateway/ATW-MBS-02_line_up_2016.pdf`
- Investigation script: `scripts/investigate_telemetry_sentinels.py`
- Sentinel values discovered during telemetry investigation (2026-04-02)
