# Investigations - Beta 2.0.0

This directory contains detailed technical investigations for issues and enhancements identified during the beta testing phase.

## Purpose

Each investigation document provides:
- Problem statement and root cause analysis
- Technical implementation details
- Testing strategies
- Risk assessment
- Implementation roadmap

## Active Investigations

### Issue #178: Anti-legionella Features Not Working
- **Status**: 📋 Ready for Implementation
- **Priority**: 🟡 Medium
- **Docs**: [issue-178-antilegionella-features.md](./issue-178-antilegionella-features.md)

**Problem**: Three anti-legionella features don't work: temperature setting reverts, 60°C validation, cycle trigger button.

**Root cause**: Code reads anti-legionella status from CONTROL registers (1030/1031) instead of STATUS registers (1084/1085). Control registers are one-shot command registers that don't reflect actual state. ATW-MBS-02 doc (Section 5.3) confirms separate status registers exist.

**Secondary**: Footnote (*9) indicates anti-legionella requires the function to be enabled on the heat pump's LCD.

**Fix**: Update `dhw_antilegionella_status` from RegisterDefinition(1030) to RegisterDefinition(1084), add new status register at 1085 for temperature read-back.

## Completed Investigations

### Issue #162: Hardware-based unique_id for Config Entry
- **Status**: ✅ Resolved in Beta.8
- **Docs**: [issue-162-hardware-unique-id.md](./issue-162-hardware-unique-id.md)

**Problem**: Config entry uses IP-based unique_id, which is unstable and allows duplicates.

**Solution**: Use gateway's hardware identifier (Modbus Input Registers 0-2) as unique_id.

**Result**: Implemented in Beta.8 with automatic migration for existing installations.

### Issue #177: Cooling Capability Detection
- **Status**: ✅ Resolved in Beta.8
- **Docs**: [issue-177-cooling-detection.md](./issue-177-cooling-detection.md)

**Problem**: Cooling features not detected on units with optional cooling hardware.

**Solution**: Fixed system_config bitmask order (regression from v1.9.x refactoring).

**Result**: Users with optional cooling hardware now properly detected.

### Issue #8: Entity Migration (1.9.x → 2.0.0)
- **Status**: ✅ Resolved in Beta.7
- **Docs**: [issue-8-entity-migration.md](./issue-8-entity-migration.md)

**Problem**: Entity unique_ids changed between versions, causing duplicate entities.

**Solution**: Automatic migration system that updates entity registry.

**Result**: Successfully deployed in Beta.7 with comprehensive testing.

### Issue #19: Repair Flow Optimization
- **Status**: ✅ Resolved in Beta.7
- **Docs**: [issue-19-repair-flow-optimization.md](./issue-19-repair-flow-optimization.md)

**Problem**: Repair flow for missing config was not functional (redirected to options instead).

**Solution**: Proper RepairFlow implementation with dedicated repairs.py platform.

**Result**: Functional repair flow following HA conventions.

## Investigation Lifecycle

1. **🔍 Investigation**: Problem identified, technical analysis in progress
2. **📋 Ready for Implementation**: Investigation complete, awaiting development
3. **🚧 In Progress**: Implementation underway
4. **✅ Resolved**: Implemented, tested, and deployed

## Document Structure

Each investigation follows this structure:

### Full Investigation Document
- Executive Summary
- Problem Statement
- Current Situation Analysis
- Technical Analysis
- Proposed Solution
- Implementation Plan
- Testing Strategy
- Risk Assessment
- Decision Log

### Quick Summary
- TL;DR
- Quick Facts
- Key Technical Points
- Impact Analysis
- Risk Assessment
- Implementation Checklist
- Decision Matrix

## Related Documentation

- [Issues Tracking](../tracking/issues-tracking.md) - All beta testing issues
- [Planned Improvements](../tracking/planned-improvements.md) - Future enhancements
- [Release Notes](../releases/) - Version-specific changelogs

## Contributing

When creating a new investigation:
1. Create both a full investigation doc and a quick summary
2. Follow the established structure
3. Update this README
4. Link from issues-tracking.md
5. Update planned-improvements.md if applicable

---

*Last updated: 2026-02-05*
