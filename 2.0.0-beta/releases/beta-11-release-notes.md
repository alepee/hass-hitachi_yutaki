# Hitachi Yutaki – DefrostGuard & Multi-Step Options Flow (v2.0.0-beta.11)

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/v2.0.0-beta.11/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/v2.0.0-beta.11)

A quality release that fixes false COP readings during defrost cycles and makes all integration settings accessible from the Configure button.

## ✨ New Features

### DefrostGuard: Centralized Defrost & Recovery Filtering
**Issue:** [#190](https://github.com/alepee/hass-hitachi_yutaki/issues/190)

COP cooling values were falsely calculated during heating mode because defrost cycles inverted the temperature delta, causing the AUTO mode detector to infer "cooling". Post-defrost recovery also produced abnormal ΔT that polluted both COP and thermal measurements.

A new `DefrostGuard` domain service implements a state machine (NORMAL → DEFROST → RECOVERY) that gates data upstream of both COP and thermal services:
- Eliminates false cooling COP values during defrost in heating mode
- Filters post-defrost recovery noise from thermal energy measurements
- Shared guard instance via coordinator for consistent filtering across all entities

### Multi-Step Options Flow
**Discussion:** [#117](https://github.com/alepee/hass-hitachi_yutaki/discussions/117)

The Configure button now walks through 4 steps mirroring the initial setup:
1. **Gateway type** selection
2. **Connection** settings (host/port)
3. **Heat pump model** selection
4. **Power supply & sensors** configuration

Users can now change their heat pump model (e.g. Yutaki S → Yutaki S Combi) without deleting and re-adding the integration. All fields are pre-filled with current values.

## 🐛 Bug Fixes

### Options Flow Data Store
The old single-page options flow was writing changes to `entry.options`, but `__init__.py` and all entities only read from `entry.data`. This meant any changes made via Configure (host, port, power supply, sensors) were **silently ignored**. The new flow correctly updates `entry.data` and triggers an integration reload.

## 📦 Installation

1. Update via HACS to v2.0.0-beta.11
2. Restart Home Assistant
3. No further action required

## ⚠️ Important Notes

- **No migration required** - direct upgrade from any previous beta
- **Yutaki S Combi users**: you can now fix your profile via Configure → step 3 (Heat Pump Model)

## 🐛 Bug Reports

If you encounter issues, please report with:
- Home Assistant version
- Heat pump model and gateway type
- Relevant logs from integration

## 🙏 Thanks

Thanks to @tijmenvanstraten for reporting the missing profile selection in the options flow.

---

**Full Changelog:** [v2.0.0-beta.10...v2.0.0-beta.11](https://github.com/alepee/hass-hitachi_yutaki/compare/v2.0.0-beta.10...v2.0.0-beta.11)
