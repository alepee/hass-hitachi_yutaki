# Hitachi Yutaki – v2.0.0-beta.7

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/v2.0.0-beta.7/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/v2.0.0-beta.7)

This release fixes critical migration issues for users upgrading from v1.9.x, ensuring a seamless upgrade experience with automatic entity migration and functional repair flows.

## 🎯 What's Fixed

### Automatic Entity Migration
**Problem:** After upgrading from v1.9.x, old entities remained as "unavailable" while new entities with different IDs were created.

**Solution:** Automatic migration system that:
- Runs transparently during integration setup
- Updates ~40 entity unique IDs to new format
- Preserves entity history and IDs
- Removes old unavailable entities

**Examples:**
- Simple: `{entry_id}_1_outdoor_temp` → `{entry_id}_outdoor_temp`
- Complex: `{entry_id}_1_thermal_power` → `{entry_id}_thermal_power_heating`

### Functional Repair Flow
**Problem:** When upgrading from v1.9.3, clicking the "Fix" button in repairs did nothing.

**Solution:** Implemented proper repair flow that:
- Opens configuration form when clicking "Fix"
- Allows selection of gateway type and profile
- Automatically reloads integration after repair
- Makes integration immediately functional

## 📦 Installation

1. Update via HACS to v2.0.0-beta.7
2. Restart Home Assistant
3. Migration runs automatically
4. If repair issue appears, click "Fix" and select your configuration

## ⚠️ Important Notes

- **Backup recommended** before upgrading
- **Entity IDs unchanged** - automations and dashboards continue to work
- **One-time migration** - only runs for entities in old format
- **Safe to run multiple times** - idempotent design

## 🐛 Bug Reports

If you encounter issues, please report with:
- Home Assistant version
- Previous integration version
- Migration logs: `grep "Entity migration" home-assistant.log`

## 🙏 Thanks

Special thanks to [@tijmenvanstraten](https://github.com/tijmenvanstraten) and [@Snoekbaarz](https://github.com/Snoekbaarz) for beta testing and feedback.

---

**Full Changelog:** [v2.0.0-beta.6...v2.0.0-beta.7](https://github.com/alepee/hass-hitachi_yutaki/compare/v2.0.0-beta.6...v2.0.0-beta.7)
