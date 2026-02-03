# Hitachi Yutaki v2.0.0 Beta Testing Documentation

This directory contains comprehensive documentation of the v2.0.0 beta testing phase, including issue tracking, release notes, and technical investigations.

---

## 📁 Directory Structure

### 📋 Tracking
Issue tracking and roadmap for future improvements.

- **[issues-tracking.md](tracking/issues-tracking.md)**: Complete list of all feedbacks and issues reported during beta testing, with status tracking
- **[planned-improvements.md](tracking/planned-improvements.md)**: Roadmap of planned improvements and enhancements for future versions

### 📦 Releases
Release history and detailed release notes for each beta version.

- **[CHANGELOG.md](releases/CHANGELOG.md)**: Complete changelog with all changes across beta versions
- **[beta-3.md](releases/beta-3.md)**: v2.0.0-beta.3 - Complete architectural overhaul (2025-10-26)
- **[beta-4.md](releases/beta-4.md)**: v2.0.0-beta.4 - Data rehydration & temperature fixes (2025-11-20)
- **[beta-5.md](releases/beta-5.md)**: v2.0.0-beta.5 - Separate heating/cooling sensors (2025-12-07)
- **[beta-6.md](releases/beta-6.md)**: v2.0.0-beta.6 - Thermal service refactoring (2026-01-22)
- **[beta-7.md](releases/beta-7.md)**: v2.0.0-beta.7 - Automatic entity migration (2026-01-23)
- **[beta-8.md](releases/beta-8.md)**: v2.0.0-beta.8 - Hardware unique_id & enhanced profiles (In Development)

### 🔍 Investigations
Detailed technical investigations and implementation documentation.

- **[issue-8-entity-migration.md](investigations/issue-8-entity-migration.md)**: Complete investigation and implementation of entity unique_id migration system
- **[issue-162-hardware-unique-id.md](investigations/issue-162-hardware-unique-id.md)**: Hardware-based config entry unique_id investigation

---

## 📊 Beta Testing Progress

| Metric | Count | Percentage |
|--------|-------|------------|
| **Total Issues Identified** | 18 | 100% |
| **Fixed** | 5 | 28% |
| **In Investigation** | 4 | 22% |
| **Not Yet Addressed** | 9 | 50% |

---

## 🎯 Beta Testing Timeline

| Version | Release Date | Focus | Status |
|---------|--------------|-------|--------|
| **v2.0.0-beta.3** | 2025-10-26 | Complete architectural overhaul | ✅ Released |
| **v2.0.0-beta.4** | 2025-11-20 | Data rehydration & temperature fixes | ✅ Released |
| **v2.0.0-beta.5** | 2025-12-07 | Separate heating/cooling sensors | ✅ Released |
| **v2.0.0-beta.6** | 2026-01-22 | Thermal service refactoring | ✅ Released |
| **v2.0.0-beta.7** | 2026-01-23 | Entity migration system | ✅ Released |
| **v2.0.0-beta.8** | TBD | Hardware unique_id & profiles | 🔄 In Development |

---

## 👥 Beta Testers

Special thanks to our beta testers for their valuable feedback:

- **tijmenvanstraten**: Hitachi Yutaki S Combi with ATW-MBS-02 gateway
- **Snoekbaarz**: Hitachi Yutaki S with ATW-MBS-02 gateway
- **ragg987**: Hitachi Yutaki S with ATW-MBS-02 gateway
- **driosalido**: Hitachi Yutaki S Combi with ATW-MBS-02 gateway

---

## 🔗 Quick Links

### External Resources
- [Main Beta Testing Discussion](https://github.com/alepee/hass-hitachi_yutaki/discussions/117)
- [GitHub Repository](https://github.com/alepee/hass-hitachi_yutaki)

### Related Documentation
- [Entity Migration Inventory](../2.0.0_entity_migration_complete.md) - Complete list of entity migrations from 1.9.x to 2.0.0
- [Entity Migration Guide](../2.0.0_entity_migration.md) - User guide for entity migration

---

## 📝 Key Achievements

### Beta.3 (2025-10-26)
- ✅ Complete architectural overhaul with hexagonal architecture
- ✅ Separate domain, adapters, and infrastructure layers
- ✅ Improved maintainability and testability

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

### Beta.7 (2026-01-23)
- ✅ Automatic entity unique_id migration system
- ✅ Resolves legacy entities issue (#8)
- ✅ Preserves entity history during migration
- ✅ Handles simple and complex migrations (key renames)

### Beta.8 (In Development)
- 🔄 Hardware-based config entry unique_id (Issue #162)
- 🔄 Enhanced heat pump profile system
- 🔄 Cooling capability detection fix (Issue #177)
- 🔄 Improved Yutampo R32 and S Combi detection

---

## 🚀 Next Steps

### Upcoming in Beta.8+
- Config flow improvements for profile selection
- UI integration of profile-specific temperature limits
- Additional improvements based on beta tester feedback

See [planned-improvements.md](tracking/planned-improvements.md) for the complete roadmap.

---

## 📖 How to Use This Documentation

1. **For Issue Tracking**: See [issues-tracking.md](tracking/issues-tracking.md)
2. **For Release Information**: Check the [releases/](releases/) directory
3. **For Technical Details**: Explore the [investigations/](investigations/) directory
4. **For Future Plans**: Review [planned-improvements.md](tracking/planned-improvements.md)

---

## 📧 Feedback

Beta testing feedback is tracked in [issues-tracking.md](tracking/issues-tracking.md). For new issues or feedback, please use the [GitHub Discussions](https://github.com/alepee/hass-hitachi_yutaki/discussions/117).

---

*Last updated: 2026-02-04*
