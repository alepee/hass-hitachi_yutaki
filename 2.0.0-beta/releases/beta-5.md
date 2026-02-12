# Hitachi Yutaki – Separate Heating/Cooling Sensors & Critical Fixes (v2.0.0-beta.5)

**Release Date**: December 7, 2025

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/v2.0.0-beta.5/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/v2.0.0-beta.5)

This release introduces **separate thermal energy sensors for heating and cooling**, providing accurate energy tracking and fixing critical setup issues. This is a **breaking change** that improves COP calculation accuracy by filtering defrost cycles and properly separating heating from cooling operations.

## ✨ What's New?

*   **Separate Thermal Energy Sensors:** The integration now provides explicit sensors for heating and cooling operations:
    *   **Real-time Power:**
        *   `thermal_power_heating`: Heating power output (when ΔT > 0) in kW
        *   `thermal_power_cooling`: Cooling power output (when ΔT < 0) in kW - only created for units with cooling circuits
    *   **Daily Energy (auto-reset at midnight):**
        *   `thermal_energy_heating_daily`: Daily heating energy production in kWh
        *   `thermal_energy_cooling_daily`: Daily cooling energy production in kWh - cooling circuits only
    *   **Total Cumulative Energy:**
        *   `thermal_energy_heating_total`: Total heating energy production in kWh
        *   `thermal_energy_cooling_total`: Total cooling energy production in kWh - cooling circuits only

*   **Improved Thermal Energy Calculation Logic:** Fixes issue [#123](https://github.com/alepee/hass-hitachi_yutaki/issues/123) with a complete rewrite of the thermal energy calculation:
    *   **Heating/Cooling Separation:** Now correctly separates heating (ΔT > 0) from cooling (ΔT < 0) operations
    *   **Defrost Cycle Filtering:** Defrost cycles are now filtered and not counted as energy production, eliminating false cooling energy measurements
    *   **Compressor-Based Measurement:** Only measures energy produced by the heat pump when the compressor is running
    *   **Universal Logic:** Works automatically for heating circuits, DHW, and pool based on water temperature delta
    *   **Accurate COP Calculations:** This results in accurate COP calculations (previously inflated by counting defrost as production)

*   **Recorder Dependency:** Added `recorder` dependency to manifest for proper Home Assistant validation and to ensure compatibility with data rehydration features.

## 🔧 Bug Fixes

*   **Setup Failure Fix:** Fixed setup failure when configuration parameters are missing by adding the required `translation_key` parameter to `async_create_issue` and corresponding translations. This resolves issue [#146](https://github.com/alepee/hass-hitachi_yutaki/issues/146) where the integration would fail to create repair issues during configuration.

*   **Hassfest Validation Fix:** Fixed hassfest validation error by adding missing `recorder` dependency to manifest. This ensures the integration passes all Home Assistant validation checks.

## ⚠️ Breaking Changes

*   **Thermal Energy Sensor Migration Required:** The old thermal energy sensors are now deprecated (disabled by default, but still available for backward compatibility):
    *   `thermal_power` → use `thermal_power_heating` instead
    *   `daily_thermal_energy` → use `thermal_energy_heating_daily` instead
    *   `total_thermal_energy` → use `thermal_energy_heating_total` instead
    *   **Action Required:** Update your Energy Dashboard configurations and automations to use the new sensor names
    *   **Why Deprecated:** The old sensors counted defrost cycles and lacked heating/cooling separation, resulting in incorrect COP values

## 📚 Technical Improvements

*   **ThermalPowerService Enhancement:** New service implementation with separate heating and cooling power tracking:
    *   Automatic mode detection based on temperature delta (ΔT)
    *   Defrost cycle filtering to prevent false measurements
    *   Compressor state validation before energy calculation
    *   Universal logic applicable to all thermal circuits (heating, DHW, pool, cooling)

*   **ThermalEnergyAccumulator Updates:** Enhanced accumulator with separate tracking for heating and cooling:
    *   Independent energy counters for heating and cooling modes
    *   Proper state restoration after Home Assistant restarts
    *   Daily reset logic for daily energy sensors

*   **Sensor Entity Builder:** Updated thermal sensor builder to conditionally create cooling sensors only when cooling circuits are detected, reducing unnecessary entities for heating-only installations.

*   **Improved Measurement Accuracy:** The new calculation logic ensures:
    *   Only real energy production is measured (compressor must be running)
    *   Defrost cycles don't inflate energy production values
    *   Heating and cooling are properly separated for accurate tracking
    *   COP calculations reflect true heat pump performance

## 📝 Important Notes

*   **Migration Required:** After upgrading to this version, you must update your Energy Dashboard and any automations that reference the old thermal energy sensors:
    *   Replace `thermal_power` with `thermal_power_heating`
    *   Replace `daily_thermal_energy` with `thermal_energy_heating_daily`
    *   Replace `total_thermal_energy` with `thermal_energy_heating_total`
    *   If you have cooling circuits, add the new cooling sensors to your dashboard

*   **COP Accuracy Improvement:** The filtering of defrost cycles means your COP values may change compared to previous versions. This is expected and reflects more accurate performance measurements.

*   **Cooling Sensor Availability:** Cooling sensors (`thermal_power_cooling`, `thermal_energy_cooling_daily`, `thermal_energy_cooling_total`) are only created for units that have cooling circuits configured. If you don't see these sensors, your unit may not support cooling mode.

*   **Backward Compatibility:** The old sensors remain available (disabled by default) for a transition period, but they will be removed in a future release. Please migrate to the new sensors as soon as possible.

*   **Recorder Dependency:** This release requires Home Assistant's Recorder to be enabled for proper operation of data rehydration features (introduced in beta.4).

## 🧪 Testing Needed

We would appreciate feedback on:

*   **Sensor Migration:** Verify that the new heating/cooling sensors appear correctly and provide accurate measurements.

*   **Energy Dashboard:** Confirm that your Energy Dashboard continues to work after migrating to the new sensor names.

*   **COP Accuracy:** Check that COP values are now more accurate and don't show inflated values during defrost cycles.

*   **Cooling Circuits:** If you have cooling circuits, verify that cooling sensors are created and track cooling energy correctly.

*   **Setup Process:** Test the setup/configuration flow to ensure the translation_key fix resolves setup failures.

*   **Defrost Filtering:** Monitor during defrost cycles to confirm that energy production is correctly paused (not counted).

## 🐛 Bug Reports

If you encounter any issues, please open a GitHub issue and include:

*   Your Home Assistant version.
*   Your configuration (heat pump model, gateway type, cooling circuits if configured).
*   Debug-level logs (especially for thermal energy calculations and sensor creation).
*   A clear description of the problem and reproduction steps.
*   Information about whether you've migrated from the old sensors to the new ones.

## 🙏 Acknowledgments

Thanks to the community for their feedback and contributions:

*   **Special Thanks:** A special thank you to [@Neuvidor](https://github.com/Neuvidor) for their investigation and contributions around COP calculation and thermal energy measurement, which were instrumental in improving the accuracy of these features.

*   **Issues Resolved:**
    *   [#123](https://github.com/alepee/hass-hitachi_yutaki/issues/123) - Thermal energy calculation improvements
    *   [#146](https://github.com/alepee/hass-hitachi_yutaki/issues/146) - Setup failure fix

*   **Beta Testers:** Thank you to all testers providing feedback on the v2.0.0-beta releases.
