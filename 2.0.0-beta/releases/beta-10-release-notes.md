# Hitachi Yutaki – Operation State Attribute & Circuit Mode Fix (v2.0.0-beta.10)

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/v2.0.0-beta.10/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/v2.0.0-beta.10)

A feature release driven by community feedback ([#183](https://github.com/alepee/hass-hitachi_yutaki/discussions/183)) that improves automation ergonomics and fixes circuit climate modes on dual-circuit installations.

## ✨ New Features

### Operation State Numeric Attribute
**Issue:** [#187](https://github.com/alepee/hass-hitachi_yutaki/issues/187)

The operation state entity now exposes the raw Modbus value (0-11) as a `code` attribute. This enables simpler automation logic using numeric comparisons instead of long state strings.

- Entity state remains human-readable (e.g. "Heating Thermo ON")
- New `code` attribute provides the numeric value (e.g. `6`)

### Conditional Circuit Climate Modes
**Issue:** [#186](https://github.com/alepee/hass-hitachi_yutaki/issues/186)

On Yutaki systems, the operating mode (heat/cool/auto) is global — it cannot differ between circuits. Previously, each circuit exposed full mode controls, which was misleading and could cause unintended side-effects.

**New behavior:**
- 🔹 **Single circuit**: unchanged — `off`/`heat`/`cool`/`auto`
- 🔹 **Two circuits**: simplified to `off`/`heat_cool` (power toggle only) — global mode is controlled via `control_unit_operation_mode`

Each circuit can now be independently turned on/off without affecting the other.

## 📦 Installation

1. Update via HACS to v2.0.0-beta.10
2. Restart Home Assistant
3. No further action required

## ⚠️ Important Notes

- **No migration required** - direct upgrade from any previous beta
- **Dual-circuit users**: climate entities will show `off`/`heat_cool` instead of `off`/`heat`/`cool`/`auto`. Use the `control_unit_operation_mode` select entity to switch between heating, cooling, and auto modes.

## 🐛 Bug Reports

If you encounter issues, please report with:
- Home Assistant version
- Heat pump model and gateway type
- Relevant logs from integration

## 🙏 Thanks

Special thanks to the user who shared detailed feedback in [discussion #183](https://github.com/alepee/hass-hitachi_yutaki/discussions/183), which directly led to these improvements.

---

**Full Changelog:** [v2.0.0-beta.9...v2.0.0-beta.10](https://github.com/alepee/hass-hitachi_yutaki/compare/v2.0.0-beta.9...v2.0.0-beta.10)
