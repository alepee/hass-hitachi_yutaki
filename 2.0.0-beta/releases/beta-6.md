# Hitachi Yutaki – Thermal Service Refactoring & Post-Cycle Improvements (v2.0.0-beta.6)

**Release Date**: January 22, 2026

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/v2.0.0-beta.6/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/v2.0.0-beta.6)

This release focuses on **code quality improvements** and **thermal energy tracking refinements**. The main highlight is a complete refactoring of the thermal service into a modular package structure, along with the introduction of a new post-cycle lock mechanism for accurate thermal inertia tracking in both heating and cooling modes.

## ✨ What's New?

* **Modular Thermal Service Architecture:** The monolithic `thermal.py` has been split into a well-organized package structure with clear separation of concerns:
  * `calculators.py`: Pure thermal power calculation functions (heating/cooling power calculations)
  * `accumulator.py`: Energy accumulation logic with post-cycle lock mechanism
  * `service.py`: Orchestration layer coordinating calculations and accumulation
  * `constants.py`: Physical constants (water specific heat, flow conversion)
  * This refactoring improves code maintainability, testability, and documentation clarity

* **New Post-Cycle Thermal Inertia Tracking:** Introduces a post-cycle lock mechanism that works consistently for both heating and cooling modes:
  * Thermal inertia energy is now correctly counted after compressor stops in **both heating and cooling modes**
  * Post-cycle lock activates when delta T drops to zero (preventing noise/fluctuations from being counted)
  * Lock releases automatically when compressor restarts
  * This ensures symmetric behavior and more accurate COP calculations by capturing all thermal energy produced by the system, including thermal inertia

* **Comprehensive Unit Tests:** Added extensive test coverage for the thermal service:
  * `test_calculators.py`: Tests for thermal power calculation functions
  * `test_accumulator.py`: Tests for energy accumulation logic including post-cycle lock behavior
  * `test_service.py`: Tests for service orchestration
  * Tests validate heating/cooling separation, defrost filtering, and post-cycle energy tracking

* **Enhanced CI/CD:** Added automated test workflow to GitHub Actions:
  * Runs tests on all pull requests and pushes
  * Ensures code quality and prevents regressions
  * Complements existing lint workflow

## 🔧 Improvements

* **Enhanced Energy Accumulation Logic:** The `ThermalEnergyAccumulator` now:
  * Tracks last heating and cooling power separately
  * Implements post-cycle lock mechanism for accurate thermal inertia tracking
  * Properly manages mode transitions and defrost cycles
  * Prevents false measurements from noise/fluctuations after delta T reaches zero

* **Cleaner Thermal Power Calculations:**
  * Removed unnecessary delta T checks from calculation functions
  * Simplified logic with pure calculation functions
  * Better separation between calculation (pure functions) and accumulation (stateful)

* **Improved Code Documentation:**
  * Comments and docstrings translated to plain English
  * Each module now has clear documentation of its purpose
  * Better inline documentation for complex logic

## 📚 Technical Details

### Refactoring Benefits

The thermal service refactoring provides several key benefits:

1. **Better Testability:** Pure calculation functions can be tested in isolation without mocking
2. **Clearer Responsibilities:** Each module has a single, well-defined purpose
3. **Easier Maintenance:** Changes to calculation logic don't affect accumulation logic and vice versa
4. **Improved Documentation:** Focused modules make it easier to understand each component

### Post-Cycle Lock Mechanism

The new post-cycle lock mechanism ensures:

* **Consistent Behavior:** Same logic applies to both heating and cooling modes
* **Accurate Energy Tracking:** Captures thermal inertia energy after compressor stops
* **Noise Prevention:** Filters out false measurements when delta T reaches zero
* **Automatic Recovery:** Lock releases when compressor restarts for next cycle

This improvement was driven by community feedback (issue #160) and ensures more accurate COP calculations by properly accounting for all thermal energy, including system inertia.

## 🧪 Testing Needed

We would appreciate feedback on:

* **Post-Cycle Energy Tracking:** Verify that energy is correctly counted after compressor stops in both heating and cooling modes
* **COP Accuracy:** Confirm that COP values remain accurate with the improved post-cycle lock logic
* **Cooling Mode:** If you have cooling circuits, verify that post-cycle energy tracking works correctly in cooling mode
* **Mode Transitions:** Test transitions between heating and cooling modes to ensure smooth operation
* **Defrost Cycles:** Confirm that defrost cycles are still properly filtered (not counted as production)

## 🐛 Bug Reports

If you encounter any issues, please open a GitHub issue and include:

* Your Home Assistant version
* Your configuration (heat pump model, gateway type, cooling circuits if configured)
* Debug-level logs (especially for thermal energy calculations)
* A clear description of the problem and reproduction steps
* Information about your specific use case (heating only vs. heating+cooling)

## 🙏 Acknowledgments

Thanks to the community for their feedback and contributions:

* **Special Thanks:** A huge thank you to @Neuvidor for their continued contributions to thermal power calculation improvements and energy accumulation logic enhancements. Their work has been instrumental in making these calculations more accurate and reliable.
* **Issues Addressed:**
  * #160 - Thermal energy calculation improvements and post-cycle lock implementation
  * #150 - Enhanced thermal power calculation and energy accumulation logic
  * #153 - Thermal service refactoring
* **Beta Testers:** Thank you to all testers providing feedback on the v2.0.0-beta releases.

## 📋 Migration Notes

**No breaking changes or migration required for this release.** This is purely an internal refactoring that maintains full backward compatibility with beta.5.

All existing thermal energy sensors continue to work exactly as before:
* `thermal_power_heating` / `thermal_power_cooling`
* `thermal_energy_heating_daily` / `thermal_energy_cooling_daily`
* `thermal_energy_heating_total` / `thermal_energy_cooling_total`

The improvements to post-cycle energy tracking may result in slightly more accurate energy measurements, but this should not require any configuration changes on your part.

---

**Full Changelog:** [v2.0.0-beta.5...v2.0.0-beta.6](https://github.com/alepee/hass-hitachi_yutaki/compare/v2.0.0-beta.5...v2.0.0-beta.6)
