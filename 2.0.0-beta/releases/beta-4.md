# Hitachi Yutaki – Data Rehydration & Temperature Fixes (v2.0.0-beta.4)

**Release Date**: November 20, 2025

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/v2.0.0-beta.4/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/v2.0.0-beta.4)

This release introduces automatic data rehydration from Home Assistant's Recorder, eliminating data loss after restarts, and fixes critical temperature unit issues for DHW and anti-legionella settings.

## ✨ What's New?

*   **Recorder-Based Data Rehydration:** COP and compressor timing sensors now automatically reconstruct their historical data from Home Assistant's Recorder on startup. This eliminates data loss after Home Assistant restarts and ensures continuity of performance measurements. The integration leverages existing sensor history instead of maintaining separate persistent storage, ensuring consistency with Home Assistant's historical data.

*   **Smart Entity Resolution:** The rehydration system intelligently resolves required sensor entities using a preference order:
    1. User-provided entities (configured via options)
    2. Built-in sensors registered by this integration (via entity registry lookup)

*   **Improved Measurement Sorting:** Fixed negative time span values in COP calculations by ensuring measurements are sorted chronologically before calculating measurement periods and energy integration.

## 🔧 Bug Fixes

*   **DHW Temperature Unit Fix:** Fixed Domestic Hot Water target temperature to be expressed in °C instead of tenths of degrees. This ensures correct temperature values are displayed and set in Home Assistant.

*   **Anti-legionella Temperature Unit Fix:** Fixed anti-legionella cycle temperature to be expressed in °C instead of tenths of degrees, ensuring accurate temperature settings for the anti-legionella cycle.

*   **Translation Validation Fix:** Removed invalid 'repair' section from translation files (en.json and fr.json) that was causing hassfest validation errors. The integration now uses standard Home Assistant issue creation without custom translations.

## 📚 Technical Improvements

*   **Enhanced COP Service:** Added `bulk_load()` method to `EnergyAccumulator` for efficient loading of historical measurements during rehydration. Improved measurement pruning logic with dedicated `_prune_old_measurements()` method.

*   **Recorder Rehydration Module:** New `recorder_rehydrate.py` adapter module providing:
    - `async_replay_cop_history()`: Reconstructs power measurements from Recorder sensor history
    - `async_replay_compressor_states()`: Rebuilds compressor timing cycles from historical data
    - Intelligent timeline reconstruction with proper state parsing and validation

*   **Sensor Entity Enhancements:** Extended `HitachiYutakiSensor` with rehydration hooks:
    - `_async_rehydrate_cop_history()`: Rebuilds COP measurement buffer on startup
    - `_async_rehydrate_compressor_history()`: Restores compressor timing cycles
    - `_async_build_cop_entity_map()`: Resolves required entity IDs for rehydration

*   **Improved Error Handling:** Rehydration failures are gracefully handled with detailed logging, ensuring the integration continues to function even if historical data cannot be reconstructed.

## 📝 Important Notes

*   **Data Continuity:** After upgrading to this version, COP and compressor timing sensors will automatically rebuild their historical data from Home Assistant's Recorder on the next startup. This process is transparent and requires no user intervention.

*   **Storage Strategy:** The integration now relies on Home Assistant's Recorder history instead of custom persistent storage for COP and compressor timing data. This eliminates redundant data storage and ensures consistency with Home Assistant's historical data.

*   **Temperature Settings:** Users who have previously configured DHW or anti-legionella temperatures may need to verify their settings after this update, as the temperature values are now correctly interpreted in °C.

*   **Backward Compatibility:** Existing configurations continue to work without changes. The rehydration system automatically detects and uses configured external entities when available.

## 🧪 Testing Needed

We would appreciate feedback on:

*   **Data Rehydration:** Verify that COP and compressor timing sensors correctly restore their historical data after Home Assistant restarts.

*   **Temperature Settings:** Confirm that DHW and anti-legionella temperature values are now correctly displayed and can be set properly.

*   **Entity Resolution:** Test that the rehydration system correctly resolves required sensor entities, especially when using external temperature or power sensors.

*   **Performance:** Verify that the rehydration process doesn't significantly impact startup time, especially for installations with extensive historical data.

## 🐛 Bug Reports

If you encounter any issues, please open a GitHub issue and include:

*   Your Home Assistant version.
*   Your configuration (heat pump model, gateway type, external sensor entities if configured).
*   Debug-level logs (especially for rehydration process and entity resolution).
*   A clear description of the problem and reproduction steps.

## 🚀 Future Benefits

*   **Zero Data Loss:** Historical performance data is preserved across Home Assistant restarts.

*   **Consistency:** Single source of truth for historical data (Home Assistant's Recorder).

*   **Reduced Storage Overhead:** No need for separate persistent storage mechanisms.

*   **Better User Experience:** Accurate temperature values for all DHW and anti-legionella settings.

Thanks for helping test this release that improves data persistence and fixes critical temperature unit issues!
