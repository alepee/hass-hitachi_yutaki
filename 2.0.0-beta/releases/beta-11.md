# Release Notes - Beta.11

**Release Date**: 2026-02-06
**Version**: 2.0.0-beta.11
**Status**: ✅ Released

---

## Overview

Beta.11 addresses two significant issues: false COP readings during defrost cycles (via a new DefrostGuard domain service) and the inability to change gateway type or heat pump profile after initial setup (via a multi-step options flow). It also fixes a silent bug where the options flow was writing to the wrong data store.

---

## What's New

### DefrostGuard: Centralized Defrost & Recovery Filtering

**Issue**: [#190](https://github.com/alepee/hass-hitachi_yutaki/issues/190)

COP cooling values were falsely calculated during heating mode because defrost cycles inverted ΔT, causing the AUTO mode detector to infer "cooling". Post-defrost recovery also produced abnormal ΔT that polluted both COP and thermal measurements.

**Solution**: A new `DefrostGuard` domain service implements a three-state machine:

| State | Condition | Effect |
|-------|-----------|--------|
| NORMAL | Defrost inactive | Data flows normally |
| DEFROST | Defrost active | All COP/thermal data blocked |
| RECOVERY | Defrost ended, ΔT abnormal | Data blocked until stable |

- Replaces the previous `is_defrosting` parameter in the thermal chain
- Filtering now handled at the entity layer via the coordinator's shared guard instance
- Comprehensive unit tests (205 lines)

**Commit**: `06e6f4f`

---

### Multi-Step Options Flow

**Discussion**: [#117](https://github.com/alepee/hass-hitachi_yutaki/discussions/117)

The Configure button previously showed a single form with host/port/power_supply/sensors — no way to change gateway type or heat pump profile. Users had to delete and re-add the integration.

**New behavior**: The options flow now mirrors the initial setup sequence:

| Step | Fields | Pre-filled |
|------|--------|------------|
| 1. Gateway | Gateway type dropdown | Current gateway |
| 2. Connection | Host, Port | Current values |
| 3. Profile | Heat pump model dropdown | Current profile |
| 4. Sensors | Power supply, voltage/power/temperature sensors | Current values |

On submit, all values are merged into `entry.data` and the integration reloads automatically.

**Commit**: `619f510`

---

### Bug Fix: Options Flow Data Store

The old options flow saved changes to `entry.options`, but `__init__.py` and all entity code exclusively read from `entry.data`. This meant changes made via Configure (host, port, power supply, external sensors) were **silently ignored** — they appeared saved in the UI but had no effect until the integration was manually removed and re-added.

The new multi-step flow correctly writes to `entry.data`.

---

## Breaking Changes

**None** - This release is fully backward compatible.

---

## Known Issues

Remaining from previous betas:
- **#176**: Auto-detection failure for some Yutaki S Combi models (now fixable via Configure)
- **#178**: Potential remaining issue — footnote (*9) requires anti-legionella function enabled on LCD
- **#179**: Migration UX could be improved
- **#166**: COP values in graphs need refinement
- **#167**: Modbus transaction ID errors (intermittent)
- **#180**: Gateway sync status stuck on "Initialising"
- **#160**: Thermal inertia in power calculation

---

## Files Changed

### New
- `domain/services/defrost_guard.py` - DefrostGuard state machine (132 lines)
- `tests/domain/services/test_defrost_guard.py` - Unit tests (205 lines)

### Modified
- `coordinator.py` - Shared DefrostGuard instance
- `domain/services/thermal/accumulator.py` - Removed `is_defrosting` parameter
- `domain/services/thermal/service.py` - Removed defrost filtering (handled upstream)
- `entities/base/sensor.py` - Uses DefrostGuard from coordinator
- `config_flow.py` - Multi-step options flow (4 steps)
- `translations/en.json` - Options flow step translations
- `translations/fr.json` - Options flow step translations (French)

---

## Installation

### Via HACS (Recommended)

1. Open HACS
2. Go to Integrations
3. Find "Hitachi Yutaki"
4. Click "Update" or "Redownload"
5. Select version `2.0.0-beta.11`
6. Restart Home Assistant

### Manual Installation

1. Download `beta-11` from GitHub
2. Copy `custom_components/hitachi_yutaki/` to your HA config
3. Restart Home Assistant

---

## Upgrade Path

### From Beta.10 → Beta.11

Direct upgrade:
1. Install Beta.11
2. Restart Home Assistant
3. Done! Yutaki S Combi users can now fix their profile via Configure → step 3.

---

## Support

- **Issues**: https://github.com/alepee/hass-hitachi_yutaki/issues
- **Discussions**: https://github.com/alepee/hass-hitachi_yutaki/discussions
- **Beta Testing**: https://github.com/alepee/hass-hitachi_yutaki/discussions/117

---

**Last Updated**: 2026-02-06
