# Hitachi Yutaki – Seamless Migration Experience (v2.0.0-beta.7)

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/v2.0.0-beta.7/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/v2.0.0-beta.7)

This release delivers a **complete migration solution** for users upgrading from v1.9.x, addressing both entity migration and repair flow functionality. The system ensures a seamless upgrade experience with no manual intervention required, preserving entity history and providing a functional repair interface for missing configuration parameters.

## ✨ What's New?

### 🔄 Automatic Entity Migration System

Resolves the "legacy entities still present" issue where users upgrading from v1.9.x found old entities remaining in their entity registry as "unavailable" while new entities with different IDs were created. The migration:
  * **100% Automatic:** Runs during integration setup - no user action required
  * **History Preserved:** Entity IDs remain unchanged, maintaining all historical data
  * **Clean Migration:** Old unavailable entities disappear automatically
  * **Safe:** Includes conflict detection and comprehensive error handling
  * **Universal:** Handles all entity types and prefixes (circuit, dhw, pool)

* **Simple Migrations (~35 entities):** Removes the Modbus slave ID from entity unique_ids
  * Example: `{entry_id}_1_outdoor_temp` → `{entry_id}_outdoor_temp`
  * Applies to: sensors, binary sensors, climate entities, switches, numbers, selects, buttons

* **Complex Migrations (~6 entities):** Removes slave ID AND renames keys for entities that changed names in 2.0.0
  * `{entry_id}_1_alarm_code` → `{entry_id}_alarm`
  * `{entry_id}_1_thermal_power` → `{entry_id}_thermal_power_heating`
  * `{entry_id}_1_daily_thermal_energy` → `{entry_id}_thermal_energy_heating_daily`
  * `{entry_id}_1_total_thermal_energy` → `{entry_id}_thermal_energy_heating_total`
  * `{entry_id}_1_circuit1_otc_method_heating` → `{entry_id}_circuit1_otc_calculation_method_heating`
  * `{entry_id}_1_circuit1_otc_method_cooling` → `{entry_id}_circuit1_otc_calculation_method_cooling`

* **Comprehensive Unit Tests:** Added extensive test coverage with 8 test cases covering:
  * Simple migrations (slave_id removal only)
  * Complex migrations (slave_id + key rename)
  * Circuit prefix handling (`circuit1_`, `circuit2_`)
  * DHW prefix handling (`dhw_`)
  * Pool prefix handling (`pool_`)
  * OTC method key renames
  * Different slave IDs (1, 2, 3, etc.)
  * Invalid format handling and edge cases

* **Complete Documentation:** Three comprehensive documentation files added:
  * Investigation report with technical implementation details
  * Device identifier and unique ID comparison tables
  * Exhaustive entity inventory with migration classification

### 🔧 Functional Repair Flow for Migration

**Critical Fix:** Resolves the non-functional repair flow button issue during migration from v1.9.3 to v2.0.0.

**The Problem:**
When upgrading from v1.9.3, users needed to provide `gateway_type` and `profile` parameters. A repair issue appeared in Home Assistant's repair system, but clicking the "Fix" button did nothing - no form appeared.

**Root Cause:**
* Missing `async_create_fix_flow()` handler function
* Incorrect architecture (repair logic in wrong module)
* Wrong import path for `RepairFlow`

**The Solution:**
* ✅ Created dedicated `repairs.py` platform following Home Assistant conventions
* ✅ Implemented `MissingConfigRepairFlow` class with proper `RepairFlow` inheritance
* ✅ Added `async_create_fix_flow()` factory function as entry point
* ✅ Automatic integration reload after repair completion
* ✅ Cleaned up `OptionsFlow` (removed repair redirect)
* ✅ Fixed import: `homeassistant.components.repairs.RepairsFlow`

**User Experience:**
1. Upgrade from v1.9.3 to beta.7
2. Integration setup fails (missing parameters)
3. Repair issue appears in **Settings → System → Repairs**
4. Click **"Fix"** → Form opens ✅ (previously did nothing)
5. Select gateway type and profile from dropdowns
6. Click **"Submit"** → Integration reloads automatically
7. Integration is immediately functional - no additional steps needed

**Technical Implementation:**
* New file: `custom_components/hitachi_yutaki/repairs.py` (100 lines)
* Modified: `custom_components/hitachi_yutaki/config_flow.py` (cleanup)
* Follows Home Assistant's official repair flow pattern
* Proper separation of concerns (repairs in dedicated platform)

## 🔧 How Entity Migration Works

The migration system operates transparently during integration setup:

1. **Detection:** Scans entity registry for entities with old format (`_{slave}_` pattern)
2. **Calculation:** Computes new unique_id (removes slave_id, applies key migrations if needed)
3. **Validation:** Checks for conflicts (if new unique_id already exists)
4. **Migration:** Updates entity registry with new unique_id
5. **Logging:** Records all actions for troubleshooting

**Safety Features:**
* Conflict detection prevents overwriting existing entities
* Try-catch around each entity migration ensures continuity
* Detailed logging at DEBUG, INFO, WARNING, and ERROR levels
* Idempotent design - safe to run multiple times
* Non-blocking - continues even if individual migrations fail

## 📋 User Experience

**For users upgrading from v1.9.x:**
1. Install v2.0.0-beta.7 via HACS
2. Restart Home Assistant
3. Migration runs automatically during integration setup
4. Old unavailable entities disappear
5. Entity history is preserved under existing entity IDs
6. Only active entities remain visible

**For users already on beta.3-6:**
* Migration detects entities are already in new format
* No changes will be made
* Safe to upgrade

## 📚 Technical Details

### New Files Added

**Entity Migration:**
* `custom_components/hitachi_yutaki/entity_migration.py` (223 lines)
  * Main migration module
  * `async_migrate_entities()`: Automatic migration orchestration
  * `_calculate_new_unique_id()`: Migration calculation with key mappings
  * `async_remove_orphaned_entities()`: Cleanup function (not enabled yet)

* `tests/test_entity_migration.py` (140 lines)
  * Comprehensive unit tests
  * All migration patterns validated

* `2.0.0-beta/investigations/issue-8-entity-migration.md` (434 lines)
  * Complete investigation report
  * Technical implementation documentation
  * Internal reference for tracking purposes

* `2.0.0_entity_migration.md` (68 lines)
  * Device identifier comparison
  * Unique ID format changes

* `2.0.0_entity_migration_complete.md` (398 lines)
  * Exhaustive entity inventory
  * Platform-by-platform breakdown
  * Migration statistics

**Repair Flow:**
* `custom_components/hitachi_yutaki/repairs.py` (100 lines)
  * Repair flows platform
  * `MissingConfigRepairFlow`: Handles missing gateway_type/profile
  * `async_create_fix_flow()`: Factory function for repair flows

* `2.0.0-beta/investigations/issue-19-repair-flow-optimization.md`
  * Complete investigation of repair flow issue
  * Architecture analysis and solution design
  * Internal reference for tracking purposes

### Files Modified

* `custom_components/hitachi_yutaki/__init__.py`
  * Added migration call before entity creation
  * Ensures migration runs early in setup process

* `custom_components/hitachi_yutaki/config_flow.py`
  * Removed repair redirect from OptionsFlow
  * Removed `async_step_repair()` method (moved to repairs.py)
  * Cleaned up unused imports

* `2.0.0-beta/tracking/issues-tracking.md`
  * Updated internal tracking status for both fixes

### Key Migrations Mapping

```python
KEY_MIGRATIONS = {
    "alarm_code": "alarm",
    "thermal_power": "thermal_power_heating",
    "daily_thermal_energy": "thermal_energy_heating_daily",
    "total_thermal_energy": "thermal_energy_heating_total",
    "otc_method_heating": "otc_calculation_method_heating",
    "otc_method_cooling": "otc_calculation_method_cooling",
}
```

## 📝 Migration Statistics

* **~35 simple migrations:** Slave ID removal only
* **~6 complex migrations:** Slave ID removal + key rename
* **~40+ new entities:** No migration needed (didn't exist in v1.9.x)

## 🧪 Testing Needed

We would appreciate feedback on:

**Entity Migration:**
* **Migration Success:** Verify that old unavailable entities disappear after upgrade from v1.9.x
* **Entity History:** Confirm that entity history is preserved after migration
* **Different Slave IDs:** Test with non-default slave IDs (if applicable)
* **Edge Cases:** Report any entities that fail to migrate properly
* **Log Analysis:** Review logs to ensure migration completes successfully

**Repair Flow:**
* **Repair Button Functionality:** Confirm that clicking "Fix" in repairs opens the form
* **Form Submission:** Verify that submitting the form reloads the integration automatically
* **Integration Functionality:** Ensure the integration works immediately after repair
* **Error Handling:** Test with invalid selections or network issues

## 🐛 Bug Reports

If you encounter any issues, please open a GitHub issue and include:

* Your Home Assistant version
* Your previous integration version (1.9.x or beta.x)
* Your configuration (heat pump model, gateway type, slave ID if not default)
* Migration logs from Home Assistant (search for "Entity migration")
* List of any entities that didn't migrate properly
* Debug-level logs if migration fails

**To check migration logs:**
```bash
grep "Entity migration" home-assistant.log
```

Expected log messages:
* `INFO: Migrated entity sensor.xxx: old_id -> new_id`
* `INFO: Entity migration completed: X entities migrated, Y failed`

## 📋 Important Notes

* **Backup Recommended:** Although migration is safe and thoroughly tested, consider backing up your Home Assistant configuration before upgrading
* **One-Time Migration:** Migration only runs once for entities in old format
* **No Breaking Changes:** This release has no breaking changes - all functionality remains the same
* **Entity IDs Unchanged:** Your entity IDs (e.g., `sensor.hitachi_outdoor_temp`) don't change, only the internal unique_id format
* **Automation Compatibility:** All existing automations, dashboards, and integrations continue to work without changes

## 🙏 Acknowledgments

Thanks to the community for their feedback and contributions:

* **Issue Reporter:** [@tijmenvanstraten](https://github.com/tijmenvanstraten) for reporting Issue #8 and providing detailed feedback on the migration experience
* **Additional Feedback:** [@Snoekbaarz](https://github.com/Snoekbaarz) for migration testing and user experience insights
* **Beta Testers:** Thank you to all testers providing feedback on the v2.0.0-beta releases and helping identify this critical issue

**Issues Resolved:**
* Legacy entities still present after upgrade from v1.9.x
* Repair flow button not functional during migration from v1.9.3

## 🔮 Future Improvements

Potential enhancements for future versions (not in beta.7):

1. **Orphan Cleanup:** Function exists but not enabled - could automatically remove orphaned entities
2. **Migration Statistics:** Create repair issue with migration results summary
3. **History Migration:** Migrate recorder history to new unique_ids (requires core HA support)
4. **Rollback Support:** Ability to rollback migrations if needed

---

**Full Changelog:** [v2.0.0-beta.6...v2.0.0-beta.7](https://github.com/alepee/hass-hitachi_yutaki/compare/v2.0.0-beta.6...v2.0.0-beta.7)
