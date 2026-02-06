# Release Notes - Beta.10

**Release Date**: 2026-02-06
**Version**: 2.0.0-beta.10
**Status**: ✅ Released

---

## Overview

Beta.10 is a feature release driven by user feedback (discussion #183). It improves automation ergonomics for the operation state entity and fixes a long-standing issue where circuit climate modes were misleading on dual-circuit installations.

---

## What's New

### Operation State: Numeric Attribute

**Issue**: [#187](https://github.com/alepee/hass-hitachi_yutaki/issues/187)

The operation state entity now exposes the raw Modbus numeric value as a `code` attribute alongside the human-readable string state.

- **State** (unchanged): `"Heating Thermo ON"` (translated string)
- **Attribute** (new): `code: 6` (raw Modbus value)

This enables simpler automation logic:
```yaml
# Before: spell out each state string
condition: "{{ states('sensor.operation_state') in ['operation_state_heat_demand_off', 'operation_state_heat_thermo_off', 'operation_state_heat_thermo_on'] }}"

# After: use numeric comparison
condition: "{{ state_attr('sensor.operation_state', 'code') | int >= 4 and state_attr('sensor.operation_state', 'code') | int <= 6 }}"
```

**Value mapping:**

| Code | State |
|------|-------|
| 0 | Off |
| 1 | No Cooling Demand |
| 2 | Cooling Thermo OFF |
| 3 | Cooling Thermo ON |
| 4 | No Heating Demand |
| 5 | Heating Thermo OFF |
| 6 | Heating Thermo ON |
| 7 | DHW OFF |
| 8 | DHW ON |
| 9 | Pool OFF |
| 10 | Pool ON |
| 11 | Alarm |

**Commit**: `8717c5b`

---

### Conditional Circuit Climate Modes

**Issue**: [#186](https://github.com/alepee/hass-hitachi_yutaki/issues/186)

On Yutaki systems, the operating mode (heat/cool/auto) is a **global** setting — you cannot have one circuit in cooling and another in heating. Previously, each circuit's climate entity exposed `heat`/`cool`/`auto`/`off` modes, which was misleading on dual-circuit installations since changing one circuit's mode would silently affect the other.

#### New Behavior

| Configuration | Modes | `set_hvac_mode` behavior |
|---|---|---|
| **Single circuit** | `off`/`heat`/`cool`/`auto` | Toggles circuit power + sets global mode (unchanged) |
| **Two circuits** | `off`/`heat_cool` | Toggles circuit power only — no side-effect on the other circuit |

With two circuits, the global operating mode is controlled exclusively via the `control_unit_operation_mode` select entity.

**Commit**: `d7982ea`

---

## Breaking Changes

**None** - This release is fully backward compatible. Existing automations using the operation state string values will continue to work. The `code` attribute is purely additive.

For dual-circuit users, the climate entity modes will change from `heat`/`cool`/`auto`/`off` to `heat_cool`/`off`. Automations referencing `HVACMode.HEAT` or `HVACMode.COOL` on circuit climate entities will need to be updated to use `HVACMode.HEAT_COOL` or the `control_unit_operation_mode` select entity instead.

---

## Known Issues

Remaining from previous betas:
- **#176**: Auto-detection failure for some Yutaki S Combi models
- **#178**: Potential remaining issue — footnote (*9) requires anti-legionella function enabled on LCD
- **#179**: Migration UX could be improved
- **#166**: COP values in graphs need refinement
- **#167**: Modbus transaction ID errors (intermittent)
- **#180**: Gateway sync status stuck on "Initialising"
- **#160**: Thermal inertia in power calculation

---

## Files Changed

### Modified
- `api/modbus/registers/atw_mbs_02.py` - Added `operation_state_code` register (raw value)
- `entities/base/sensor.py` - Added `_get_operation_state_attributes()` and dispatch
- `entities/base/climate.py` - Conditional HVAC modes based on `multi_circuit` flag
- `entities/circuit/climate.py` - Detect active circuit count and pass to entity

---

## Installation

### Via HACS (Recommended)

1. Open HACS
2. Go to Integrations
3. Find "Hitachi Yutaki"
4. Click "Update" or "Redownload"
5. Select version `2.0.0-beta.10`
6. Restart Home Assistant

### Manual Installation

1. Download `beta-10` from GitHub
2. Copy `custom_components/hitachi_yutaki/` to your HA config
3. Restart Home Assistant

---

## Upgrade Path

### From Beta.9 → Beta.10

Direct upgrade:
1. Install Beta.10
2. Restart Home Assistant
3. Done! Dual-circuit users will see simplified climate modes automatically.

---

## Support

- **Issues**: https://github.com/alepee/hass-hitachi_yutaki/issues
- **Discussions**: https://github.com/alepee/hass-hitachi_yutaki/discussions
- **Beta Testing**: https://github.com/alepee/hass-hitachi_yutaki/discussions/117

---

**Last Updated**: 2026-02-06
