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

### Issue #162: MAC-based unique_id for Config Entry
- **Status**: 🔍 Ready for Implementation
- **Priority**: 🔴 High
- **Target**: Beta.8 or v2.1.0
- **Docs**: 
  - [Full Investigation](./issue-162-mac-based-unique-id.md)
  - [Quick Summary](./issue-162-summary.md)

**Problem**: Config entry uses IP-based unique_id, which is unstable and allows duplicates.

**Solution**: Use gateway's MAC address from ARP table as unique_id.

**Status**: Technical investigation complete, prototype implemented, tests passing.

## Completed Investigations

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

*Last updated: 2026-01-24*
