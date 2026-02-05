# Release Notes - Beta.9

**Release Date**: 2026-02-06
**Version**: 2.0.0-beta.9
**Status**: ✅ Released

---

## Overview

Beta.9 is a bugfix release focusing on two issues: incorrect Modbus register usage for the anti-legionella binary sensor and missing translations in the configuration flow.

---

## What's New

No new features in this release.

---

## Bug Fixes

### Anti-legionella Binary Sensor Reading Incorrect Registers

**Issue**: [#178](https://github.com/alepee/hass-hitachi_yutaki/issues/178)

The anti-legionella binary sensor was reading from CONTROL registers (R/W, address range 0–49) instead of STATUS registers (R, address range 50–99). This caused the sensor to reflect the *command* state rather than the *actual running* state.

#### Root Cause

The ATW-MBS-02 gateway exposes two register ranges:
- **CONTROL registers** (Holding Registers, 0–49): Write commands to the heat pump
- **STATUS registers** (Holding Registers, 50–99): Read actual state from the heat pump

The anti-legionella sensor was mapped to the control register (`R_ANTILEGIONELLA`), which only reflects whether the command was sent, not whether the cycle is actually running.

#### Fix

Changed the register mapping to use `S_ANTILEGIONELLA` (status register) instead of `R_ANTILEGIONELLA` (control register).

**Commit**: `8115f95`

---

### Config Flow Missing Translations

The configuration flow displayed raw keys instead of human-readable labels for:
- **Gateway type selector**: showed `gateway_type` as field label and `modbus_atw_mbs_02` as value
- **Profile selector**: showed `profile` as field label and raw keys like `yutaki_s80` as values
- **Step misalignment**: the `user` step translation contained connection details instead of gateway selection

#### What Was Wrong

1. No `translation_key` on `gateway_type` and `profile` `SelectSelector` widgets
2. Translation file `config.step.user` contained data for the `gateway_config` step
3. Missing `config.step.gateway_config` and `config.step.profile` translations
4. Missing `selector.gateway_type` and `selector.profile` translations
5. Missing `switch.high_demand` in French translations

#### Fix

- Added `translation_key="gateway_type"` and `translation_key="profile"` to selectors in `config_flow.py`
- Added selector translations with human-readable model names (e.g., "Yutaki S80", "Modbus ATW-MBS-02")
- Fixed step translations to match actual config flow structure
- Added missing French translation for `switch.high_demand`

**Commit**: `813d61f`

---

## Breaking Changes

**None** - This release is fully backward compatible.

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
- `config_flow.py` - Added `translation_key` to gateway and profile selectors
- `translations/en.json` - Added gateway_type/profile selector translations, fixed step translations
- `translations/fr.json` - Same as en.json + added missing `switch.high_demand`

### Previously Changed (beta.8 post-release)
- `entities/dhw/binary_sensors.py` - Anti-legionella register fix (STATUS instead of CONTROL)

---

## Installation

### Via HACS (Recommended)

1. Open HACS
2. Go to Integrations
3. Find "Hitachi Yutaki"
4. Click "Update" or "Redownload"
5. Select version `2.0.0-beta.9`
6. Restart Home Assistant

### Manual Installation

1. Download `beta-9` from GitHub
2. Copy `custom_components/hitachi_yutaki/` to your HA config
3. Restart Home Assistant

---

## Upgrade Path

### From Beta.8 → Beta.9

Direct upgrade:
1. Install Beta.9
2. Restart Home Assistant
3. Done! Config flow will now show proper translated labels.

---

## Support

- **Issues**: https://github.com/alepee/hass-hitachi_yutaki/issues
- **Discussions**: https://github.com/alepee/hass-hitachi_yutaki/discussions
- **Beta Testing**: https://github.com/alepee/hass-hitachi_yutaki/discussions/117

---

**Last Updated**: 2026-02-06
