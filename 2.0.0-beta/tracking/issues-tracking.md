# Feedbacks & Issues - Beta Testing v2.0.0

## Summary Statistics

- **Total issues identified**: 23 (19 from beta testing + 4 enhancements)
- **Fixed**: 11 (48%)
- **In investigation**: 2 (9%)
- **Not yet addressed**: 10 (43%)
- **GitHub open issues**: 14 total
  - **Beta v2.0.0 bugs (7)**: [#166](https://github.com/alepee/hass-hitachi_yutaki/issues/166), [#167](https://github.com/alepee/hass-hitachi_yutaki/issues/167), [#176](https://github.com/alepee/hass-hitachi_yutaki/issues/176), [#178](https://github.com/alepee/hass-hitachi_yutaki/issues/178), [#179](https://github.com/alepee/hass-hitachi_yutaki/issues/179), [#180](https://github.com/alepee/hass-hitachi_yutaki/issues/180), [#160](https://github.com/alepee/hass-hitachi_yutaki/issues/160)
  - **Enhancements (7)**: [#77](https://github.com/alepee/hass-hitachi_yutaki/issues/77), [#81](https://github.com/alepee/hass-hitachi_yutaki/issues/81), [#96](https://github.com/alepee/hass-hitachi_yutaki/issues/96), [#102](https://github.com/alepee/hass-hitachi_yutaki/issues/102), [#137](https://github.com/alepee/hass-hitachi_yutaki/issues/137), [#161](https://github.com/alepee/hass-hitachi_yutaki/issues/161), [#162](https://github.com/alepee/hass-hitachi_yutaki/issues/162)

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
- **Status**: 🔄 **Partially addressed in beta.8**
- **Progress**:
  - ✅ Profile system enhanced with `max_circuits` property
  - ✅ S Combi profile now correctly defines `max_circuits=1`
  - ✅ S Combi detection checks all circuits (not just circuit 1)
  - ⏳ Remaining: config_flow suggestion logic + coordinator intersection
- **Note**: Full fix requires config_flow and coordinator updates (planned for beta.9)

### Issue 3: Cooling support missing (regression from v1.9)
- **GitHub**: [#177 (Consolidated with issue 18)](https://github.com/alepee/hass-hitachi_yutaki/issues/177)
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-09 (first report), 2026-01-08 (follow-up as issue 18)
- **Root cause**: System_config bitmask order incorrectly swapped during v2.0.0 refactoring
- **Description**: Cooling features that were available in v1.9 are missing in beta.3+
- **Status**: ✅ **Fixed in beta.8**
- **Fix**: Corrected MASKS_CIRCUIT bit order in `atw_mbs_02.py` to match ATW-MBS-02 documentation
- **Commit**: `6183bee`
- **Data**: Modbus gateway dump from discussion #115 (system_config=21) confirmed the issue
- **Investigation**: [Issue 177 Investigation](../investigations/issue-177-cooling-detection.md)

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
- **GitHub**: [#171](https://github.com/alepee/hass-hitachi_yutaki/issues/171) ✅ CLOSED
- **Reporter**: tijmenvanstraten
- **Date**: 2025-11-21
- **Description**: "Temperature set corrected" sensor shows 500°C instead of 50°C (10x too high)
- **Status**: ✅ **Fixed in beta.7**
- **Resolution**: User confirmed temperature displays correct value
- **Tested by**: tijmenvanstraten (Yutaki S Combi)

---

## Issues from v2.0.0-beta.4/beta.5

### Issue 16: Cannot change DHW temperature via water heater entity
- **GitHub**: [#173](https://github.com/alepee/hass-hitachi_yutaki/issues/173) ✅ CLOSED
- **Reporter**: tijmenvanstraten
- **Date**: 2025-12-21
- **Description**: Setting DHW temperature to 55°C via water heater entity fails, reverts to 50°C after 1-2 minutes
- **Status**: ✅ **Fixed in beta.7**
- **Resolution**: User confirmed DHW temperature control works correctly in beta.7
- **Tested by**: tijmenvanstraten (Yutaki S Combi 2019)

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

### Beta.8 (Upcoming)
- ✅ **Hardware-based unique_id for config entries** (Issue #162 implemented)
- ✅ Prevents duplicate config entries for same physical gateway
- ✅ Survives DHCP IP changes
- ✅ Automatic migration for existing installations
- ✅ Graceful fallback if MAC unavailable
- ✅ Cross-platform support (Linux, macOS, Windows)
- ✅ **Cooling capability detection fix** (Issue #177)
- ✅ Corrected system_config bitmask order (regression from v1.9.x)
- ✅ Users with optional cooling hardware now properly detected
- ✅ **Enhanced profile system** (Issues #176, #81, #77 - partial)
- ✅ New profile properties: dhw_min/max_temp, max_circuits, supports_cooling, max_water_outlet_temp
- ✅ Explicit hardware capabilities per model (S, S Combi, S80, M, Yutampo R32)
- ✅ Fixed Yutampo R32 detection (unit_model=1 + DHW only)
- ✅ Fixed S Combi detection (checks all circuits, not just circuit 1)
- ✅ Unit tests for profile detection
- 📋 Manual testing pending

---

## Upcoming

### Beta.9+ (Future)
- See [Planned Improvements](./planned-improvements.md) for planned enhancements

---

## Enhancement Requests

### Issue #162: MAC-based unique_id for Config Entry
- **GitHub**: [#162](https://github.com/alepee/hass-hitachi_yutaki/issues/162)
- **Type**: Enhancement
- **Date**: 2026-01-23
- **Priority**: 🔴 HIGH
- **Investigation**: [issue-162-mac-based-unique-id.md](../investigations/issue-162-mac-based-unique-id.md)
- **Testing Guide**: [issue-162-testing-guide.md](../investigations/issue-162-testing-guide.md)
- **Description**: Add MAC-based unique_id for config entry to prevent duplicates
- **Current situation**: unique_id based on `{IP}_{slave_id}` is not stable (DHCP) and allows duplicates
- **Implemented solution**: Use gateway's MAC address as unique_id via ARP table lookup
- **Status**: ✅ **Implemented in Beta.8** - 📋 GitHub issue à fermer
- **Target release**: Beta.8
- **Implementation**:
  - ✅ MAC retrieval function (`utils.py`)
  - ✅ Config flow integration
  - ✅ Automatic migration for existing installations
  - ✅ Graceful fallback if MAC unavailable
  - ✅ Unit tests (8 tests)
  - ✅ Linter passed
  - 📋 Manual testing pending
- **Benefits**:
  - ✅ Prevents duplicate config entries for same physical gateway
  - ✅ Stable identifier (survives IP changes)
  - ✅ Home Assistant best practices compliance
  - ✅ Prepares for future DHCP discovery

---

## Issues from v2.0.0-beta.7+

### Issue #180: Gateway sync status stuck on "Initialising"
- **GitHub**: [#180](https://github.com/alepee/hass-hitachi_yutaki/issues/180)
- **Reporter**: À identifier
- **Date**: 2026-01-25
- **Description**: ATW-MBS-02 gateway_sync_status entity stuck on "Initialising" state
- **Status**: ❌ Not addressed
- **Priority**: 🟡 MEDIUM - Affects monitoring but not functionality

### Issue #160: Thermal inertia in power calculation
- **GitHub**: [#160](https://github.com/alepee/hass-hitachi_yutaki/issues/160)
- **Reporter**: À identifier
- **Date**: 2026-01-21
- **Description**: Thermal power calculation should consider thermal inertia, not just compressor frequency
- **Status**: 🔍 **In investigation**
- **Priority**: 🟡 MEDIUM - Affects calculation accuracy
- **Notes**: Related to thermal energy tracking improvements in Beta.6

### Issue #161: Two3 sensor support for buffer tank systems
- **GitHub**: [#161](https://github.com/alepee/hass-hitachi_yutaki/issues/161)
- **Type**: Enhancement
- **Reporter**: À identifier
- **Date**: 2026-01-22
- **Description**: Add support for reading Two3 sensor for systems with a buffer tank
- **Status**: ❌ Not addressed
- **Priority**: 🟢 LOW - Feature request

---

## Older Enhancement Requests (Pre-Beta)

### Issue #137: Circuit thermostat displays 0°C
- **GitHub**: [#137](https://github.com/alepee/hass-hitachi_yutaki/issues/137)
- **Date**: 2025-11-19
- **Description**: Circuit thermostat displays 0°C as target temperature
- **Status**: ❌ Not addressed

### Issue #102: Hitachi 8kW Split_Unit (2023) support
- **GitHub**: [#102](https://github.com/alepee/hass-hitachi_yutaki/issues/102)
- **Date**: 2025-09-16
- **Description**: Request to add support for Hitachi 8kW Split_Unit (2023)
- **Status**: ❌ Not addressed - Needs hardware access

### Issue #96: HC-A16MB support request
- **GitHub**: [#96](https://github.com/alepee/hass-hitachi_yutaki/issues/96)
- **Date**: 2025-09-01
- **Description**: Heat pump support request for HC-A16MB model
- **Status**: ❌ Not addressed - Needs hardware access

### Issue #81: Autodetect Connected Heat Pump Type
- **GitHub**: [#81](https://github.com/alepee/hass-hitachi_yutaki/issues/81)
- **Date**: 2025-07-22
- **Description**: Feature request to auto-detect connected heat pump type
- **Status**: 🔄 Partially addressed - Auto-detection implemented but has issues (see #176)

### Issue #77: Yutampo DHW max temp limited to 55°C
- **GitHub**: [#77](https://github.com/alepee/hass-hitachi_yutaki/issues/77)
- **Date**: 2025-07-19
- **Description**: DHW feature only allows max temp of 55°C, HA UI thermostat allows setting of 60°C
- **Status**: 🔄 **Partially addressed in beta.8**
- **Progress**:
  - ✅ Yutampo R32 profile now defines `dhw_max_temp=55` and `entity_overrides` with `boost_temp=75`
  - ⏳ Remaining: UI needs to use these profile values for temperature limits

---

## Related Documentation

- [Planned Improvements](./planned-improvements.md) - Planned improvements and enhancements
- [Issue 8: Entity Migration](../investigations/issue-8-entity-migration.md) - Complete investigation and implementation
- [Issue 19: Repair Flow Optimization](../investigations/repair-flow-optimization.md) - Investigation of non-functional repair flow for 1.9.x → 2.0.0 migration
- [Issue 162: MAC-based unique_id](../investigations/issue-162-mac-based-unique-id.md) - Investigation of MAC-based config entry identification

---

## GitHub Issue Consolidation

As of 2026-01-27, related issues have been consolidated into fewer, more comprehensive GitHub issues:

### Beta v2.0.0 Consolidated Issues
- **#176**: Auto-detection failure (Circuit 2 + Model name) ← Local issues 1, 2
- **#177**: ~~Cooling features not working~~ ✅ FIXED in beta.8 ← Local issues 3, 18
- **#178**: Anti-legionella features ← Local issues 10, 15, 17
- **#179**: Migration UX issues ← Local issues 11, 12

### Beta v2.0.0 Standalone Bug Issues
- **#166**: COP values in graphs ← Local issue 7
- **#167**: Modbus transaction ID errors ← Local issue 9
- **#171**: ~~Temperature corrected sensor error~~ ✅ CLOSED ← Local issue 14
- **#173**: ~~Cannot change DHW temperature~~ ✅ CLOSED ← Local issue 16
- **#180**: Gateway sync status stuck (NEW)
- **#160**: Thermal inertia consideration (NEW)

### Enhancement Requests
- **#162**: MAC-based unique_id ✅ Implemented - À fermer
- **#161**: Two3 sensor support (NEW)
- **#137**: Circuit thermostat 0°C display
- **#102**: Hitachi 8kW Split_Unit support
- **#96**: HC-A16MB support
- **#81**: Auto-detect heat pump type (partially addressed)
- **#77**: Yutampo DHW max temp

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
- **15 open issues** on GitHub (8 bugs + 7 enhancements)

---

*Last updated: 2026-02-03 - Enhanced profile system implemented (issues #176, #81, #77 partial)*
