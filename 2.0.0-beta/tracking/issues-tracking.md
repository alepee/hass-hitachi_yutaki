# Feedbacks & Issues - Beta Testing v2.0.0

## Summary Statistics

- **Total issues identified**: 20 (19 from beta testing + 1 enhancement)
- **Fixed**: 6 (30%)
- **In investigation**: 5 (25%)
- **Not yet addressed**: 9 (45%)
- **Tracked on GitHub**: 9 open issues (consolidated from 13 individual reports + 1 enhancement)
  - 4 consolidated issues: [#176](https://github.com/alepee/hass-hitachi_yutaki/issues/176), [#177](https://github.com/alepee/hass-hitachi_yutaki/issues/177), [#178](https://github.com/alepee/hass-hitachi_yutaki/issues/178), [#179](https://github.com/alepee/hass-hitachi_yutaki/issues/179)
  - 4 standalone issues: [#166](https://github.com/alepee/hass-hitachi_yutaki/issues/166), [#167](https://github.com/alepee/hass-hitachi_yutaki/issues/167), [#171](https://github.com/alepee/hass-hitachi_yutaki/issues/171), [#173](https://github.com/alepee/hass-hitachi_yutaki/issues/173)
  - 1 enhancement: [#162](https://github.com/alepee/hass-hitachi_yutaki/issues/162)

---

## Issues from v2.0.0-beta.3

### Issues 1 & 2: Auto-detection failure (Circuit 2 + Model name)
- **GitHub**: [#176 (Consolidated)](https://github.com/alepee/hass-hitachi_yutaki/issues/176)
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09
- **Root cause**: Auto-detection mechanism fails for Yutaki S Combi
- **Impact**: 
  - Issue 1: Circuit 2 entities incorrectly created for single-circuit model
  - Issue 2: Generic "Hitachi Yutaki" name instead of specific model
- **Status**: ❌ Not addressed
- **Note**: Both issues stem from same profile detection failure

### Issue 3: Cooling support missing (regression from v1.9)
- **GitHub**: [#177 (Consolidated with issue 18)](https://github.com/alepee/hass-hitachi_yutaki/issues/177)
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09 (first report), 2026-01-08 (follow-up as issue 18)
- **Root cause**: Cooling capability auto-detection failure
- **Description**: Cooling features that were available in v1.9 are missing in beta.3+
- **Status**: ❌ Not addressed
- **Data**: Modbus gateway dump available (discussion #115)
- **Priority**: 🔴 HIGH - Regression affecting users with cooling hardware

### Issue 4: DHW temperature decimal error
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09
- **Description**: DHW target temperature displays 5°C instead of 50°C (factor of 10 error)
- **Status**: ✅ **Fixed in beta.4**
- **Fix**: Temperature now correctly expressed in °C instead of tenths

### Issue 5: Anti-legionella temperature decimal error
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09
- **Description**: Anti-legionella temperature displays 5°C instead of 50°C (factor of 10 error)
- **Status**: ✅ **Fixed in beta.4**
- **Fix**: Temperature now correctly expressed in °C instead of tenths

### Issue 6: Identical COP values for DHW and Space Heating
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09
- **Description**: COP calculations for DHW and Space Heating show the same value (2.62) even when only space heating is active
- **Status**: ✅ **Partially fixed in beta.4**
- **Fix**: Improved measurement sorting for COP calculations
- **Notes**: May require further investigation

### Issue 7: COP values always present in graph
- **GitHub**: [#166](https://github.com/alepee/hass-hitachi_yutaki/issues/166)
- **Reporter**: tijmenvanstraten
- **Date**: 2025-10-27
- **Description**: COP values remain visible in graphs even when heating is off (actual entity value is "unknown")
- **Status**: ❌ Not addressed
- **Notes**: Affects graph visualization, not actual data

### Issue 8: Legacy entities still present
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
- **Documentation**: See [Issue 8 Investigation](../investigations/issue-8-entity-migration.md)

### Issue 9: Modbus transaction ID errors
- **GitHub**: [#167](https://github.com/alepee/hass-hitachi_yutaki/issues/167)
- **Reporter**: tijmenvanstraten
- **Date**: 2025-10-30
- **Description**: Intermittent modbus errors: "request ask for transaction_id=X but got id=Y, Skipping"
- **Status**: 🔍 **In investigation**
- **Logs**: Multiple occurrences with different transaction IDs
- **Impact**: Potential data reading failures

### Issues 10, 15, 17: Anti-legionella features not working
- **GitHub**: [#178 (Consolidated)](https://github.com/alepee/hass-hitachi_yutaki/issues/178)
- **Reporter**: tijmenvanstraten
- **Dates**: 2025-11-09, 2025-11-21, 2025-12-21
- **Root cause**: Modbus register write issues for anti-legionella features
- **Impact**:
  - Issue 10: Cannot modify anti-legionella temperature (reverts to previous value)
  - Issue 15: Temperature validation enforces 60-80°C range (too restrictive?)
  - Issue 17: Start cycle button doesn't work (cycle doesn't start)
- **Status**: ❌ Not addressed
- **Note**: All three involve writing to anti-legionella registers

---

## Issues from v2.0.0-beta.3 (Migration Experience)

### Issues 11 & 12: Migration UX issues (beta.3)
- **GitHub**: [#179 (Consolidated)](https://github.com/alepee/hass-hitachi_yutaki/issues/179)
- **Reporter**: Snoekbaarz
- **Date**: 2025-11-03 (beta.3)
- **Root cause**: Config flow and migration issues in beta.3
- **Impact**:
  - Issue 11: Error message on HA restart after installation
  - Issue 12: Integration unresponsive after gateway/profile selection
- **Status**: ⚠️ **Needs verification** - May be fixed in beta.7 (Issues 8 and 19)
- **Note**: Beta.7 improvements (entity migration, repair flow) may have resolved these

### Issue 13: Heating elements sensor request
- **Reporter**: Snoekbaarz
- **Date**: 2025-11-20
- **Description**: Request for sensors to show status of 3 heating elements
- **Status**: ✅ **Resolved**
- **Resolution**: User found existing sensor `control_unit_space_heater` that shows when elements are active
- **Notes**: Not in modbus register, existing sensor sufficient

---

## Issues from v2.0.0-beta.4

### Issue 14: Temperature set corrected sensor error
- **GitHub**: [#171](https://github.com/alepee/hass-hitachi_yutaki/issues/171)
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-21
- **Description**: "Temperature set corrected" sensor shows 500°C instead of 50°C (10x too high)
- **Status**: ❌ Not addressed
- **Notes**: Regression from DHW temperature fix (issue 4) - sensor incorrectly affected

---

## Issues from v2.0.0-beta.4/beta.5

### Issue 16: Cannot change DHW temperature via water heater entity
- **GitHub**: [#173](https://github.com/alepee/hass-hitachi_yutaki/issues/173)
- **Reporter**: tijmenvanstraten
- **Date**: 2025-12-21
- **Description**: Setting DHW temperature to 55°C via water heater entity fails, reverts to 50°C after 1-2 minutes
- **Status**: 🔍 **In investigation**
- **Notes**: 
  - Heat pump display remains at 50°C (doesn't receive command)
  - User confirmed no time schedule is running
  - Heat pump supports temperatures above 50°C (Yutaki S Combi 2019)
  - Remote control is enabled on heat pump
  - Other settings (DHW boost) work correctly

### Issue 18: See Issue 3
- Consolidated into Issue 3 (Cooling support) - same root cause
- Reported in beta.5 as continuation of beta.3 issue

### Issue 19: Repair flow not functional for 1.9.3 → 2.0.0 migration
- **Reporter**: Internal (code review)
- **Date**: 2026-01-23
- **Description**: Migration from v1.9.3 to v2.0.0 requires user to provide `gateway_type` and `profile` parameters. A repair issue is created, but clicking the "Fix" button does nothing - no repair form appears.
- **Status**: ✅ **Fixed in beta.7**
- **Root cause**: Missing `async_create_fix_flow()` handler function and incorrect architecture
- **Fix**: 
  - Created dedicated `repairs.py` platform following Home Assistant conventions
  - Implemented `MissingConfigRepairFlow` class inheriting from `RepairsFlow`
  - Added `async_create_fix_flow()` factory function as module-level entry point
  - Integrated automatic integration reload after repair completion
  - Removed repair redirect logic from `OptionsFlow`
  - Fixed import to use `homeassistant.components.repairs.RepairsFlow`
- **Technical details**:
  - Repair issue created with `is_fixable=True` in `__init__.py`
  - Home Assistant requires `repairs.py` platform with `async_create_fix_flow()` function
  - RepairFlow must be imported from `homeassistant.components.repairs` (not `data_entry_flow`)
- **Investigation document**: [Issue 19 Investigation](../investigations/issue-19-repair-flow-optimization.md)
- **Priority**: 🔴 **CRITICAL** - Was blocking migration for all 1.9.x users (now resolved)

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
- ✅ **Functional repair flow for 1.9.3 → 2.0.0 migration** (Issue 19 fixed)
- ✅ Created dedicated `repairs.py` platform following HA conventions
- ✅ Implemented `MissingConfigRepairFlow` with proper RepairFlow inheritance
- ✅ Added `async_create_fix_flow()` factory function
- ✅ Automatic integration reload after repair completion
- ✅ Cleaned up OptionsFlow (removed repair redirect)

---

## Upcoming

### Beta.8+ (Future)
- See [Planned Improvements](./planned-improvements.md) for planned enhancements

---

## Enhancement Requests

### Issue #162: MAC-based unique_id for Config Entry
- **GitHub**: [#162](https://github.com/alepee/hass-hitachi_yutaki/issues/162)
- **Type**: Enhancement
- **Date**: 2026-01-23
- **Priority**: 🔴 HIGH
- **Investigation**: [issue-162-mac-based-unique-id.md](../investigations/issue-162-mac-based-unique-id.md)
- **Description**: Add MAC-based unique_id for config entry to prevent duplicates
- **Current situation**: unique_id based on `{IP}_{slave_id}` is not stable (DHCP) and allows duplicates
- **Proposed solution**: Use gateway's MAC address as unique_id via ARP table lookup
- **Status**: 🔍 In investigation
- **Target release**: Beta.8 or v2.1.0
- **Benefits**:
  - ✅ Prevents duplicate config entries for same physical gateway
  - ✅ Stable identifier (survives IP changes)
  - ✅ Home Assistant best practices compliance
  - ✅ Prepares for future DHCP discovery

---

## Related Documentation

- [Planned Improvements](./planned-improvements.md) - Planned improvements and enhancements
- [Issue 8: Entity Migration](../investigations/issue-8-entity-migration.md) - Complete investigation and implementation
- [Issue 19: Repair Flow Optimization](../investigations/repair-flow-optimization.md) - Investigation of non-functional repair flow for 1.9.x → 2.0.0 migration
- [Issue 162: MAC-based unique_id](../investigations/issue-162-mac-based-unique-id.md) - Investigation of MAC-based config entry identification

---

## GitHub Issue Consolidation

As of 2026-01-23, related issues have been consolidated into fewer, more comprehensive GitHub issues:

### Consolidated Issues
- **#176**: Auto-detection failure (Circuit 2 + Model name) ← Local issues 1, 2
- **#177**: Cooling features not working ← Local issues 3, 18
- **#178**: Anti-legionella features ← Local issues 10, 15, 17
- **#179**: Migration UX issues ← Local issues 11, 12

### Standalone Issues
- **#166**: COP values in graphs ← Local issue 7
- **#167**: Modbus transaction ID errors ← Local issue 9
- **#171**: Temperature corrected sensor error ← Local issue 14
- **#173**: Cannot change DHW temperature ← Local issue 16
- **#162**: MAC-based unique_id for config entry (enhancement)

### Benefits of Consolidation
- ✅ Focus on root causes instead of symptoms
- ✅ Better context and technical analysis
- ✅ Easier to track related problems
- ✅ More efficient investigation and fixing

## Notes

- Main testing discussion: https://github.com/alepee/hass-hitachi_yutaki/discussions/117
- Beta testers: tijmenvanstraten (Yutaki S Combi), Snoekbaarz (Yutaki S)
- Testing focus: Auto-detection, cooling support, temperature settings, COP accuracy
- GitHub Issues milestone: https://github.com/alepee/hass-hitachi_yutaki/milestone/2
- **9 open issues** on GitHub (4 consolidated + 4 standalone + 1 enhancement)

---

*Last updated: 2026-01-24 - Added enhancement #162 (MAC-based unique_id)*
