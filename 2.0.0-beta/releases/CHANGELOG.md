# v2.0.0 Beta Changelog

This changelog summarizes the evolution of the v2.0.0 beta releases.

---

## [v2.0.0-beta.7] - 2026-01-23

### Added
- 🔄 **Automatic entity migration system** for seamless upgrade from v1.9.x (Issue #8)
  - Migrates entity unique_ids from old format (with slave_id) to new format
  - Handles simple migrations (~35 entities) and complex migrations with key renames (~6 entities)
  - Supports circuit, DHW, and pool entity prefixes
  - Preserves entity history and IDs
- 🔧 **Functional repair flow** for 1.9.3 → 2.0.0 migration (Issue #19)
  - Created dedicated `repairs.py` platform following HA conventions
  - Implemented `MissingConfigRepairFlow` with proper RepairFlow inheritance
  - Added `async_create_fix_flow()` factory function
  - Automatic integration reload after repair completion
- ✅ Comprehensive unit tests for entity migration
- 📚 Complete investigation documentation for both issues

### Fixed
- **Critical**: Repair flow button not working during migration (Issue #19)
  - Missing `async_create_fix_flow()` handler function
  - Incorrect architecture (repair logic in wrong module)
  - Wrong import path for RepairFlow
- Legacy entities appearing as "unavailable" after upgrade (Issue #8)

### Improved
- Cleaned up OptionsFlow (removed repair redirect)
- Better separation of concerns (repairs in dedicated platform)
- Migration runs automatically during integration setup

### Technical
- New file: `custom_components/hitachi_yutaki/entity_migration.py` (223 lines)
- New file: `custom_components/hitachi_yutaki/repairs.py` (100 lines)
- New file: `tests/test_entity_migration.py` (140 lines)
- Modified: `custom_components/hitachi_yutaki/__init__.py` (migration call)
- Modified: `custom_components/hitachi_yutaki/config_flow.py` (cleanup)

### Breaking Changes
- None - migration is fully automatic

---

## [v2.0.0-beta.6] - 2026-01-22

### Added
- 🏗️ Modular thermal service architecture (split into calculators, accumulator, service, constants)
- 🔄 Post-cycle thermal inertia tracking for both heating and cooling modes
- ✅ Comprehensive unit tests for thermal service
- 🚀 Automated test workflow in GitHub Actions CI/CD

### Improved
- Enhanced energy accumulation logic with post-cycle lock mechanism
- Cleaner thermal power calculations (pure functions)
- Code documentation translated to English
- Better separation between calculation and accumulation logic

### Technical
- Prevents false measurements from noise after delta T reaches zero
- Captures thermal inertia energy accurately
- Symmetric behavior for heating and cooling modes

### Contributors
- Special thanks to @Neuvidor for thermal power calculation improvements

---

## [v2.0.0-beta.5] - 2025-12-07

### Added
- ⚡ Separate thermal energy sensors for heating and cooling
  - `thermal_power_heating` / `thermal_power_cooling`
  - `thermal_energy_heating_daily` / `thermal_energy_cooling_daily`
  - `thermal_energy_heating_total` / `thermal_energy_cooling_total`
- 🧪 Defrost cycle filtering (not counted as energy production)
- 📦 Recorder dependency in manifest

### Fixed
- Setup failure when configuration parameters are missing (issue #146)
- Hassfest validation error for missing recorder dependency

### Breaking Changes
- ⚠️ Old thermal energy sensors deprecated (migration required):
  - `thermal_power` → `thermal_power_heating`
  - `daily_thermal_energy` → `thermal_energy_heating_daily`
  - `total_thermal_energy` → `thermal_energy_heating_total`

### Improved
- More accurate COP calculations (defrost no longer inflates values)
- Heating/cooling separation based on temperature delta
- Compressor-based measurement (only when running)
- Universal logic for heating circuits, DHW, pool, and cooling

### Issues Resolved
- #123 - Thermal energy calculation improvements
- #146 - Setup failure fix

### Contributors
- Special thanks to @Neuvidor for COP calculation contributions

---

## [v2.0.0-beta.4] - 2025-11-20

### Added
- 💾 Recorder-based data rehydration for COP and compressor timing sensors
- 🔍 Smart entity resolution (user-provided → built-in sensors)
- 📊 Improved measurement sorting (chronological order)

### Fixed
- 🌡️ DHW temperature unit (now in °C instead of tenths)
- 🌡️ Anti-legionella temperature unit (now in °C instead of tenths)
- ✅ Translation validation (removed invalid 'repair' section)

### Improved
- Enhanced COP service with `bulk_load()` method
- New `recorder_rehydrate.py` adapter module
- Better error handling for rehydration failures
- Zero data loss across Home Assistant restarts

### Technical
- `async_replay_cop_history()`: Reconstructs power measurements
- `async_replay_compressor_states()`: Rebuilds timing cycles
- Eliminates redundant storage (uses HA Recorder history)

---

## [v2.0.0-beta.3] - 2025-10-26

### Added
- 🏛️ Complete hexagonal architecture implementation
- 🔌 Robust Modbus connection recovery with exponential backoff
- 🏗️ Domain-driven entity structure (circuit, compressor, control_unit, dhw, gateway, etc.)
- 📋 Comprehensive business API (HitachiApiClient)
- 🔨 Builder pattern for type-safe entity creation
- 📚 Specialized documentation for each architectural layer

### Improved
- Centralized data conversion logic
- Logical Modbus register organization
- Enhanced entity identifiers (r134a_ → secondary_compressor_)
- Code quality: sensor.py reduced from 1657 to ~150 lines

### Technical
- Pure business logic in domain layer (100% testable)
- Adapters bridge domain with Home Assistant
- Platform files act as pure orchestrators
- Prepared for HTTP-based gateways and persistent storage

### Issues Resolved
- #118 - Modbus connection recovery

### Breaking Changes
- Major architectural refactoring (user-facing functionality unchanged)
- Developers should review new architecture documentation

---

## Legend

- 🏛️ Architecture
- 🔌 Connectivity
- 🌡️ Temperature
- 💾 Data Persistence
- ⚡ Energy Tracking
- 🧪 Testing
- 📦 Dependencies
- 🔍 Detection
- ⚠️ Breaking Change
- ✅ Fix
- 🚀 CI/CD

---

## Upcoming

### v2.0.0-beta.7 (In Development)

#### Added
- 🔄 Automatic entity migration system for seamless upgrade from v1.9.x
- ✅ Comprehensive unit tests for migration logic (8 test cases)
- 📚 Complete migration documentation and investigation reports

#### Fixed
- Issue #8 - Legacy entities appearing as "unavailable" after upgrade

#### Improved
- Zero manual intervention required for entity migration
- Conflict detection and error handling for safe migrations
- Detailed logging for troubleshooting migration issues
- Support for simple migrations (slave_id removal) and complex migrations (slave_id + key rename)

#### Technical
- `async_migrate_entities()`: Automatic unique_id migration
- `_calculate_new_unique_id()`: Migration calculation with key mappings
- Handles all entity types and prefixes (circuit, dhw, pool)
- Idempotent and non-blocking migration process

#### Issues Resolved
- #8 - Entity migration from 1.9.x to 2.0.0

---

### v2.0.0-beta.8+ (Future)
- See [Planned Improvements](../tracking/planned-improvements.md)

---

*For detailed release notes, see individual `beta-X.md` files.*
