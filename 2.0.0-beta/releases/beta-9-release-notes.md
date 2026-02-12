# Hitachi Yutaki – Anti-legionella & Config Flow Translations (v2.0.0-beta.9)

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/v2.0.0-beta.9/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/v2.0.0-beta.9)

A bugfix release that corrects the anti-legionella binary sensor and adds missing translations to the configuration flow.

## 🐛 Bug Fixes

### Anti-legionella Binary Sensor
**Issue:** [#178](https://github.com/alepee/hass-hitachi_yutaki/issues/178)

The anti-legionella binary sensor was reading from CONTROL registers (commands) instead of STATUS registers (actual state). It now correctly reflects whether an anti-legionella cycle is actually running.

### Config Flow Translations
The configuration flow displayed raw keys instead of human-readable labels:
- **Before:** `gateway_type` / `modbus_atw_mbs_02` / `yutaki_s80`
- **After:** "Gateway Type" / "Modbus ATW-MBS-02" / "Yutaki S80"

**Fixed:**
- ✅ Gateway type selector now shows "Modbus ATW-MBS-02"
- ✅ Profile selector now shows proper model names (Yutaki S, S Combi, S80, M, Yutampo R32)
- ✅ All config flow steps have proper titles and descriptions (EN + FR)
- ✅ Missing French translation for "High Demand" switch added

## 📦 Installation

1. Update via HACS to v2.0.0-beta.9
2. Restart Home Assistant
3. No further action required

## ⚠️ Important Notes

- **No breaking changes** - fully backward compatible
- **No migration required** - direct upgrade from any previous beta

## 🐛 Bug Reports

If you encounter issues, please report with:
- Home Assistant version
- Heat pump model and gateway type
- Relevant logs from integration

## 🙏 Thanks

Special thanks to beta testers for their continued feedback.

---

**Full Changelog:** [v2.0.0-beta.8...v2.0.0-beta.9](https://github.com/alepee/hass-hitachi_yutaki/compare/v2.0.0-beta.8...v2.0.0-beta.9)
