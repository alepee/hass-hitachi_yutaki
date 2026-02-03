# Hitachi Yutaki – Hardware Identity & Enhanced Profiles (v2.0.0-beta.8)

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/v2.0.0-beta.8/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/v2.0.0-beta.8)

This release improves integration robustness with hardware-based identification, enhanced heat pump profiles, and fixes cooling detection for units with optional cooling hardware.

## ✨ What's New

### Hardware-based Config Entry Identification
Config entries now use gateway hardware identifiers (Modbus Input Registers 0-2) instead of IP+slave.

**Benefits:**
- Prevents duplicate config entries for the same gateway
- Survives DHCP IP address changes
- Works in Docker, VMs, and all HA installation types
- Automatic migration for existing installations

### Enhanced Heat Pump Profile System
Profiles now define explicit hardware capabilities per model:

| Model | DHW | Circuits | Cooling | Max Water Temp |
|-------|-----|----------|---------|----------------|
| Yutaki S | 30-55°C | 2 | ✅ (kit) | 60°C |
| Yutaki S Combi | 30-55°C | 1 | ✅ (kit) | 60°C |
| Yutaki S80 | 30-75°C | 2 | ❌ | 80°C |
| Yutaki M | 30-55°C | 2 | ✅ (native) | 60°C |
| Yutampo R32 | 30-55°C | 0 | ❌ | - |

**Detection improvements:**
- Fixed Yutampo R32 detection (unit_model=1 + DHW-only)
- Fixed S Combi detection (checks all circuits)
- Corrected unit_model mapping (0-3 per documentation)

## 🐛 Bug Fixes

### Cooling Capability Detection
**Problem:** Cooling features not detected on units with optional cooling hardware (e.g., Yutaki S Combi with cooling kit).

**Cause:** `system_config` bitmask order was incorrectly swapped during v2.0.0 refactoring.

**Fixed:**
- ✅ "Cool" option now available in operation mode
- ✅ Cooling thermal power/energy sensors created
- ✅ Climate entities show proper HVAC modes

## 📦 Installation

1. Update via HACS to v2.0.0-beta.8
2. Restart Home Assistant
3. Hardware-based unique_id is added automatically
4. All entities and history preserved

## ⚠️ Important Notes

- **No action required** - all migrations are automatic
- **Entity IDs unchanged** - automations and dashboards continue to work
- **Fallback available** - if hardware ID can't be read, falls back to IP+slave

## 🐛 Bug Reports

If you encounter issues, please report with:
- Home Assistant version
- Heat pump model and gateway type
- Relevant logs from integration

## 🙏 Thanks

Special thanks to [@tijmenvanstraten](https://github.com/tijmenvanstraten) and [@Snoekbaarz](https://github.com/Snoekbaarz) for continued beta testing and feedback.

---

**Full Changelog:** [v2.0.0-beta.7...v2.0.0-beta.8](https://github.com/alepee/hass-hitachi_yutaki/compare/v2.0.0-beta.7...v2.0.0-beta.8)
