# v2.0.0-beta.7 Release Notes

**Release Date**: 2026-01-23  
**Status**: Ready for Testing

---

## 🎯 Overview

Beta.7 introduces **automatic entity migration** to solve the "legacy entities still present" issue reported by users upgrading from v1.9.x. This release ensures a seamless upgrade experience with no manual intervention required.

---

## ✨ What's New

### 🔄 Automatic Entity Migration System

**Issue Resolved**: [#8](https://github.com/alepee/hass-hitachi_yutaki/issues/8) - Legacy entities appearing as "unavailable" after upgrade

When upgrading from v1.9.x to v2.0.0, the integration now automatically migrates entity unique IDs to the new format. This eliminates duplicate entities and preserves your entity history.

**Key Features**:
- ✅ **100% Automatic**: No user action required
- ✅ **History Preserved**: Entity IDs remain unchanged
- ✅ **Clean Migration**: Old unavailable entities disappear
- ✅ **Safe**: Conflict detection and error handling
- ✅ **Comprehensive**: Handles all entity types and prefixes

**Migration Types Supported**:

1. **Simple Migrations** (~35 entities)
   - Removes Modbus slave ID from unique_id
   - Example: `{entry_id}_1_outdoor_temp` → `{entry_id}_outdoor_temp`

2. **Complex Migrations** (~6 entities)
   - Removes slave ID AND renames key
   - Examples:
     - `{entry_id}_1_alarm_code` → `{entry_id}_alarm`
     - `{entry_id}_1_thermal_power` → `{entry_id}_thermal_power_heating`
     - `{entry_id}_1_otc_method_heating` → `{entry_id}_otc_calculation_method_heating`

3. **Prefix Support**
   - Circuit entities: `circuit1_`, `circuit2_`
   - DHW entities: `dhw_`
   - Pool entities: `pool_`

**How It Works**:
1. Migration runs automatically during integration setup
2. Scans entity registry for old format entities
3. Calculates new unique_id (with key migrations if needed)
4. Updates entity registry
5. Logs all actions for troubleshooting

**User Experience**:
- Upgrade from 1.9.x to beta.7
- Restart Home Assistant
- Migration runs automatically
- Old unavailable entities disappear
- Entity history is preserved
- Only active entities remain

---

## 🧪 Testing

### Comprehensive Unit Tests

Added complete test coverage for entity migration:
- ✅ Simple migrations (slave_id removal)
- ✅ Complex migrations (slave_id + key rename)
- ✅ Circuit prefix handling
- ✅ DHW prefix handling
- ✅ Pool prefix handling
- ✅ OTC method key renames
- ✅ Different slave IDs (1, 2, 3, etc.)
- ✅ No migration needed cases
- ✅ Invalid format handling

Run tests: `pytest tests/test_entity_migration.py`

---

## 📚 Documentation

### New Documentation Files

1. **`2.0.0-beta/investigations/issue-8-entity-migration.md`**
   - Complete investigation report
   - Technical implementation details
   - Migration examples
   - Testing recommendations

2. **`2.0.0_entity_migration.md`**
   - Device identifier comparison
   - Unique ID format changes
   - Summary of changes

3. **`2.0.0_entity_migration_complete.md`**
   - Exhaustive entity inventory
   - Platform-by-platform breakdown
   - Migration classification
   - Statistics

---

## 🔧 Technical Details

### Files Added

- `custom_components/hitachi_yutaki/entity_migration.py` (223 lines)
  - Main migration module
  - `async_migrate_entities()`: Main migration function
  - `_calculate_new_unique_id()`: Migration logic
  - `async_remove_orphaned_entities()`: Cleanup function (not enabled)

- `tests/test_entity_migration.py` (140 lines)
  - Comprehensive unit tests
  - All migration patterns covered

### Files Modified

- `custom_components/hitachi_yutaki/__init__.py`
  - Added migration call before entity creation
  - Ensures migration runs early in setup process

- `2.0.0-beta/tracking/issues-tracking.md`
  - Updated Issue #8 status to "Fixed in beta.7"

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

### Safety Features

- **Conflict Detection**: Checks if new unique_id already exists
- **Error Handling**: Try-catch around each entity migration
- **Detailed Logging**: DEBUG, INFO, WARNING, ERROR levels
- **Idempotent**: Safe to run multiple times
- **Non-blocking**: Continues on errors

---

## 🐛 Issues Resolved

- **Issue #8**: Legacy entities still present after upgrade to v2.0.0-beta
  - Reporter: tijmenvanstraten
  - Status: ✅ **Fixed**
  - Solution: Automatic entity unique_id migration

---

## 📊 Migration Statistics

- **~35 simple migrations**: Slave ID removal only
- **~6 complex migrations**: Slave ID + key rename
- **~40+ new entities**: No migration needed (didn't exist in 1.9.x)

---

## ⚠️ Important Notes

### For Users Upgrading from 1.9.x

1. **Backup Recommended**: Although migration is safe, consider backing up your Home Assistant configuration
2. **Check Logs**: After restart, check logs for migration summary
3. **Verify Entities**: Confirm old unavailable entities are gone
4. **Report Issues**: If migration fails for any entity, please report with logs

### For Users Already on Beta.3-6

- Migration will detect that entities are already in new format
- No changes will be made
- Safe to upgrade

### Logging

Check migration results in Home Assistant logs:
```bash
grep "Entity migration" home-assistant.log
```

Expected log messages:
- `INFO: Migrated entity sensor.xxx: old_id -> new_id`
- `INFO: Entity migration completed: X entities migrated, Y failed`

---

## 🚀 Upgrade Path

### From v1.9.x

1. Install v2.0.0-beta.7 via HACS
2. Restart Home Assistant
3. Migration runs automatically
4. Verify entities in Developer Tools → States
5. Check logs for migration summary

### From v2.0.0-beta.3-6

1. Install v2.0.0-beta.7 via HACS
2. Restart Home Assistant
3. No migration needed (already in new format)
4. Enjoy the update!

---

## 🔮 Future Improvements

Potential enhancements for future versions (not in beta.7):

1. **Orphan Cleanup**
   - Function exists but not enabled
   - Could automatically remove orphaned entities

2. **Migration Statistics**
   - Create repair issue with migration results
   - Help users understand what was migrated

3. **History Migration**
   - Migrate recorder history to new unique_ids
   - Requires core HA support

4. **Rollback Support**
   - Ability to rollback migrations
   - Safety net for unexpected issues

---

## 🙏 Acknowledgments

- **tijmenvanstraten**: For reporting Issue #8 and providing detailed feedback
- **Snoekbaarz**: For additional testing and migration experience feedback
- **Beta Testers**: For helping identify and validate the migration solution

---

## 📝 Related Documentation

- [Issue #8 Investigation](../investigations/issue-8-entity-migration.md)
- [Complete Entity Migration Inventory](../../2.0.0_entity_migration_complete.md)
- [Issues Tracking](../tracking/issues-tracking.md)

---

## 🔗 Links

- **Discussion**: https://github.com/alepee/hass-hitachi_yutaki/discussions/117
- **Issue Tracker**: https://github.com/alepee/hass-hitachi_yutaki/issues
- **Documentation**: https://github.com/alepee/hass-hitachi_yutaki

---

**Happy Testing! 🎉**

*Please report any issues or feedback in the discussion thread.*
