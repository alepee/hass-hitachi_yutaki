# Documentation Restructure Design

**Date**: 2026-03-02
**Status**: Approved

## Problem

The repository has 27 documentation files scattered across multiple locations with inconsistent language (French/English mix), overlapping content, and unclear audience targeting. Architecture is documented 5 times in different places. In-code READMEs duplicate content from `documentation/`. CLAUDE.md mixes AI governance with tutorials.

## Decisions

- **Language**: Everything in English
- **Private/**: Not touched
- **Audience**: Contributors (human + AI) are the priority
- **In-code READMEs**: Removed, content centralized in `docs/`
- **GitHub templates**: Added (issue templates + PR template)

## Target Structure

```
README.md                              # User-facing (install, config, troubleshooting)
CONTRIBUTING.md                        # Lightweight, points to docs/development/
CHANGELOG.md                          # Unchanged
CLAUDE.md                             # Rules & conventions only (~150 lines)

docs/
├── architecture.md                    # Hexagonal overview (merges 5 sources)
├── development/
│   ├── getting-started.md             # Setup, prerequisites, first PR
│   ├── adding-entities.md             # Step-by-step entity creation guide
│   ├── modbus-registers.md            # Reading/adding registers
│   └── profiles.md                    # Profile system, adding a model
├── reference/
│   ├── entity-patterns.md             # Builder pattern, base classes, patterns
│   ├── domain-services.md             # COP, thermal, timing, ports/adapters
│   └── quality-scale.md              # HA quality scale assessment
├── gateway/
│   ├── README.md                      # Gateway comparison
│   ├── atw-mbs-02.md                 # ATW register map
│   ├── hc-a-mb.md                    # HC-A register map
│   ├── scan-reference.md             # Scanning/debug reference
│   ├── datasheets/                    # Hitachi gateway PDFs
│   └── pac/                           # Hitachi PAC PDFs
└── plans/                             # Design docs

.github/
├── ISSUE_TEMPLATE/
│   ├── bug_report.yml
│   └── feature_request.yml
└── pull_request_template.md
```

## Migration Map

### Files moved (content preserved, translated if needed)

| Source | Destination | Notes |
|--------|------------|-------|
| `documentation/architecture.md` | `docs/architecture.md` | Translated FR→EN, merged with layer READMEs |
| `documentation/entities.md` | `docs/reference/entity-patterns.md` | Translated FR→EN |
| `documentation/quality-scale-assessment.md` | `docs/reference/quality-scale.md` | Moved as-is |
| `documentation/gateway/README.md` | `docs/gateway/README.md` | Moved as-is |
| `documentation/gateway/ATW-MBS-02.md` | `docs/gateway/atw-mbs-02.md` | Moved as-is |
| `documentation/gateway/HC-A-MB.md` | `docs/gateway/hc-a-mb.md` | Moved as-is |
| `documentation/gateway/scan-reference.md` | `docs/gateway/scan-reference.md` | Moved as-is |
| `documentation/gateway/*.pdf` | `docs/gateway/datasheets/` | Moved |
| `documentation/pac/*.pdf` | `docs/gateway/pac/` | Moved |

### Files absorbed and deleted

| Source | Absorbed into | Notes |
|--------|--------------|-------|
| `custom_components/hitachi_yutaki/domain/README.md` | `docs/architecture.md` | Domain layer section |
| `custom_components/hitachi_yutaki/adapters/README.md` | `docs/architecture.md` | Adapters layer section |
| `custom_components/hitachi_yutaki/entities/README.md` | `docs/architecture.md` + `docs/reference/entity-patterns.md` | Split across two docs |
| `TODO-hc-a-mb-registers.md` | GitHub issue or `docs/gateway/hc-a-mb.md` | Remove from root |

### Files rewritten

| File | Change |
|------|--------|
| `CLAUDE.md` | Slimmed from ~305 to ~150 lines. Architecture explanations, patterns, and examples moved to `docs/`. Keeps: rules, commands, conventions, pointers. |
| `CONTRIBUTING.md` | Slimmed. Points to `docs/development/getting-started.md` for details. |

### New files created

| File | Content |
|------|---------|
| `docs/development/getting-started.md` | Setup, prerequisites, running tests, running HA dev, repo structure |
| `docs/development/adding-entities.md` | Step-by-step guide for adding entities by business domain |
| `docs/development/modbus-registers.md` | Register definitions, CONTROL vs STATUS, adding new registers |
| `docs/development/profiles.md` | Profile system, model detection, adding a new profile |
| `docs/reference/domain-services.md` | COP calculation, thermal energy, timing, defrost guard |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | HA version, integration version, heat pump model, gateway, logs |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Description, use case, affected model |
| `.github/pull_request_template.md` | Checklist: tests, changelog, lint, description |

## CLAUDE.md Scope After Rewrite

### Stays (rules & conventions)
- Project overview (3-4 lines)
- Development commands (make targets)
- Architecture rules (NEVER/ALWAYS per layer, no explanations)
- Key domain concepts (short list + pointers to docs/)
- Circuit climate architecture (trap-specific, critical for AI)
- Entity migration context (v2.0.0)
- Translations (Weblate, en.json source of truth)
- Code quality standards
- Testing commands
- Dependencies
- Branch strategy
- Git conventions

### Moves out
- Layer structure tree → `docs/architecture.md`
- Entity builder pattern examples → `docs/reference/entity-patterns.md`
- Common patterns (code examples) → `docs/development/` + `docs/reference/`
- Documentation file list → removed (self-evident with new structure)

## README.md

Coherence pass only — no structural rewrite. Update any internal links to point to new `docs/` paths.
