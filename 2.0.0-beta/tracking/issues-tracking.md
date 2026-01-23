# Feedbacks & Issues - Beta Testing v2.0.0

This document tracks all feedbacks and issues reported during the v2.0.0 beta testing phase.

## Summary Statistics

- **Total issues identified**: 18
- **Fixed**: 5 (28%)
- **In investigation**: 4 (22%)
- **Not yet addressed**: 9 (50%)

---

## Issues from v2.0.0-beta.3

### Issue #1: Circuit 2 incorrectly added
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09
- **Description**: Circuit 2 entities are created even though the Yutaki S Combi doesn't have a second circuit
- **Status**: ❌ Not addressed
- **Related**: Auto-detection mechanism

### Issue #2: Generic model name displayed
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09
- **Description**: Integration displays "Hitachi Yutaki" instead of detecting the specific model (Yutaki S Combi)
- **Status**: ❌ Not addressed
- **Related**: Auto-detection mechanism

### Issue #3: Cooling support missing
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09
- **Description**: Cooling features that were available in v1.9 are missing in beta.3
- **Status**: ❌ Not addressed
- **Notes**: User has optional cooling installed on Yutaki S Combi

### Issue #4: DHW temperature decimal error
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09
- **Description**: DHW target temperature displays 5°C instead of 50°C (factor of 10 error)
- **Status**: ✅ **Fixed in beta.4**
- **Fix**: Temperature now correctly expressed in °C instead of tenths

### Issue #5: Anti-legionella temperature decimal error
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09
- **Description**: Anti-legionella temperature displays 5°C instead of 50°C (factor of 10 error)
- **Status**: ✅ **Fixed in beta.4**
- **Fix**: Temperature now correctly expressed in °C instead of tenths

### Issue #6: Identical COP values for DHW and Space Heating
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09
- **Description**: COP calculations for DHW and Space Heating show the same value (2.62) even when only space heating is active
- **Status**: ✅ **Partially fixed in beta.4**
- **Fix**: Improved measurement sorting for COP calculations
- **Notes**: May require further investigation

### Issue #7: COP values always present in graph
- **Reporter**: tijmenvanstraten
- **Date**: 2025-10-27
- **Description**: COP values remain visible in graphs even when heating is off (actual entity value is "unknown")
- **Status**: ❌ Not addressed
- **Notes**: Affects graph visualization, not actual data

### Issue #8: Legacy entities still present
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09
- **Description**: v1.9 entities remain listed but show as "unavailable" after migration to beta.3
- **Status**: ✅ **Fixed in beta.7**
- **Fix**: Automatic entity unique_id migration implemented
- **Details**: 
  - Created `entity_migration.py` module for automatic migration
  - Handles simple migrations (slave_id removal)
  - Handles complex migrations (slave_id removal + key rename)
  - Supports all entity types and prefixes (circuit, dhw, pool)
  - Migration runs automatically on integration setup
  - Comprehensive unit tests added
- **Documentation**: See [Issue #8 Investigation](../investigations/issue-8-entity-migration.md)

### Issue #9: Modbus transaction ID errors
- **Reporter**: tijmenvanstraten
- **Date**: 2025-10-30
- **Description**: Intermittent modbus errors: "request ask for transaction_id=X but got id=Y, Skipping"
- **Status**: 🔍 **In investigation**
- **Logs**: Multiple occurrences with different transaction IDs
- **Impact**: Potential data reading failures

### Issue #10: Cannot modify anti-legionella temperature
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09
- **Description**: Attempting to change anti-legionella temperature fails and reverts to previous value
- **Status**: ❌ Not addressed
- **Notes**: Related to issue #4 (decimal error) - may have been resolved in beta.4

---

## Issues from v2.0.0-beta.3 (Migration Experience)

### Issue #11: Error on restart after installation
- **Reporter**: Snoekbaarz
- **Date**: 2025-11-03
- **Description**: Error message appears after Home Assistant restart following beta.3 installation
- **Status**: ❌ Not addressed
- **Notes**: Can be resolved by clicking through, but indicates migration issue

### Issue #12: Integration not responding after config
- **Reporter**: Snoekbaarz
- **Date**: 2025-11-03
- **Description**: After selecting gateway and profile, integration becomes unresponsive, requiring restart
- **Status**: ❌ Not addressed
- **Notes**: Part of migration experience that needs smoothing

### Issue #13: Heating elements sensor request
- **Reporter**: Snoekbaarz
- **Date**: 2025-11-20
- **Description**: Request for sensors to show status of 3 heating elements
- **Status**: ✅ **Resolved**
- **Resolution**: User found existing sensor `control_unit_space_heater` that shows when elements are active
- **Notes**: Not in modbus register, existing sensor sufficient

---

## Issues from v2.0.0-beta.4

### Issue #14: Temperature set corrected sensor error
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-21
- **Description**: "Temperature set corrected" sensor shows 500°C instead of 50°C (10x too high)
- **Status**: ❌ Not addressed
- **Notes**: Seems the DHW temperature fix (#4) affected this sensor incorrectly

### Issue #15: Anti-legionella temperature validation
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-21
- **Description**: Cannot set anti-legionella temperature below 60°C - error message says must be between 60-80°C
- **Status**: 🔍 **Question pending**
- **Question**: Is this validation from the integration or from the heat pump itself?
- **Notes**: Needs clarification on expected behavior

---

## Issues from v2.0.0-beta.4/beta.5

### Issue #16: Cannot change DHW temperature via climate entity
- **Reporter**: tijmenvanstraten
- **Date**: 2025-12-21
- **Description**: Setting DHW temperature to 55°C via climate entity fails, reverts to 50°C after 1-2 minutes
- **Status**: 🔍 **In investigation**
- **Notes**: 
  - Heat pump display remains at 50°C (doesn't receive command)
  - User confirmed no time schedule is running
  - Heat pump supports temperatures above 50°C (Yutaki S Combi 2019)
  - Remote control is enabled on heat pump
  - Other settings (DHW boost) work correctly

### Issue #17: Anti-legionella cycle button not working
- **Reporter**: tijmenvanstraten
- **Date**: 2025-12-21
- **Description**: "Start anti-legionella cycle" button can be pressed but cycle doesn't start (or is immediately turned off)
- **Status**: ❌ Not addressed
- **Notes**: May be related to Issue #15 (temperature validation)

### Issue #18: Cooling sensors not created despite cooling hardware
- **Reporter**: tijmenvanstraten
- **Date**: 2026-01-08
- **Description**: Heat pump has optional cooling installed but cooling sensors are not created in beta.5
- **Status**: 🔍 **In investigation**
- **Likely cause**: Auto-detection failure
- **Action**: Modbus gateway dump requested (provided in discussion #115)
- **Notes**: Related to Issue #3

---

## Improvements Delivered

### Beta.4 (2025-11-20)
- ✅ DHW temperature unit fix (now in °C)
- ✅ Anti-legionella temperature unit fix (now in °C)
- ✅ Improved measurement sorting for COP calculations
- ✅ Automatic Recorder-based rehydration for COP and timing sensors

### Beta.5 (2025-12-07)
- ✅ Separate thermal energy sensors for heating and cooling
- ✅ Improved thermal energy calculation (defrost filtering)
- ✅ Setup failure fix (translation_key)

### Beta.6 (2026-01-22)
- ✅ Thermal service refactoring (modular architecture)
- ✅ Post-cycle thermal inertia tracking
- ✅ Comprehensive unit tests
- ✅ Enhanced CI/CD with automated testing

---

### Beta.7 (2026-01-23)
- ✅ Automatic entity unique_id migration system
- ✅ Handles simple migrations (slave_id removal)
- ✅ Handles complex migrations (slave_id + key rename)
- ✅ Comprehensive unit tests for migration logic

---

## Upcoming

### Beta.8+ (Future)
- See [Planned Improvements](./planned-improvements.md) for planned enhancements

---

## Related Documentation

- [Planned Improvements](./planned-improvements.md) - Planned improvements and enhancements
- [Issue #8: Entity Migration](../investigations/issue-8-entity-migration.md) - Complete investigation and implementation

---

## Notes

- Main testing discussion: https://github.com/alepee/hass-hitachi_yutaki/discussions/117
- Beta testers: tijmenvanstraten (Yutaki S Combi), Snoekbaarz (Yutaki S)
- Testing focus: Auto-detection, cooling support, temperature settings, COP accuracy

---

*Last updated: 2026-01-22*
