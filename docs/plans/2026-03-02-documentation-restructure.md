# Documentation Restructure — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate all documentation into a unified `docs/` structure, standardize to English, slim CLAUDE.md to rules-only, and add GitHub templates.

**Architecture:** Move gateway docs as-is, merge+translate architecture docs from 5 sources into one, create new development guides and reference docs from existing code knowledge, slim root files, add GitHub templates.

**Tech Stack:** Markdown, GitHub YAML issue templates

**Design doc:** `docs/plans/2026-03-02-documentation-restructure-design.md`

---

### Task 1: Create directory structure and move gateway docs

**Files:**
- Create: `docs/gateway/datasheets/` (directory)
- Create: `docs/gateway/pac/` (directory)
- Create: `docs/development/` (directory)
- Create: `docs/reference/` (directory)
- Move: `documentation/gateway/README.md` → `docs/gateway/README.md`
- Move: `documentation/gateway/ATW-MBS-02.md` → `docs/gateway/atw-mbs-02.md`
- Move: `documentation/gateway/HC-A-MB.md` → `docs/gateway/hc-a-mb.md`
- Move: `documentation/gateway/scan-reference.md` → `docs/gateway/scan-reference.md`
- Move: `documentation/gateway/*.pdf` → `docs/gateway/datasheets/`
- Move: `documentation/pac/*.pdf` → `docs/gateway/pac/`

**Step 1: Create directories**

```bash
mkdir -p docs/gateway/datasheets docs/gateway/pac docs/development docs/reference
```

**Step 2: Move gateway markdown files**

```bash
git mv documentation/gateway/README.md docs/gateway/README.md
git mv documentation/gateway/ATW-MBS-02.md docs/gateway/atw-mbs-02.md
git mv documentation/gateway/HC-A-MB.md docs/gateway/hc-a-mb.md
git mv documentation/gateway/scan-reference.md docs/gateway/scan-reference.md
```

**Step 3: Move PDF files**

```bash
git mv documentation/gateway/ATW-MBS-02_line_up_2016.pdf docs/gateway/datasheets/
git mv documentation/gateway/ATW-MBS-02_before_line_up_2016.pdf docs/gateway/datasheets/
git mv documentation/gateway/HC-A16MB.pdf docs/gateway/datasheets/
git mv documentation/pac/yutaki_S80_PMFR0648_rev0_03-23.pdf docs/gateway/pac/
```

**Step 4: Update internal links in moved gateway files**

In `docs/gateway/README.md`, update PDF references to point to `datasheets/` subfolder.

**Step 5: Commit**

```bash
git add docs/gateway/
git commit -m "docs: move gateway documentation to docs/gateway/"
```

---

### Task 2: Write docs/architecture.md

Merge and translate content from 5 sources into one unified architecture document:
- `documentation/architecture.md` (French, 332 lines) — main structure
- `custom_components/hitachi_yutaki/domain/README.md` (English, 112 lines) — domain details
- `custom_components/hitachi_yutaki/adapters/README.md` (English, 135 lines) — adapter details
- `custom_components/hitachi_yutaki/entities/README.md` (English, 195 lines) — entity details
- CLAUDE.md Architecture section (English) — layer rules

**Files:**
- Create: `docs/architecture.md`

**Step 1: Write the document**

Structure:
1. **Overview** — Hexagonal Architecture (Ports and Adapters) with domain-driven entity organization (3-4 sentences)
2. **Layer Diagram** — ASCII diagram from `documentation/architecture.md` lines 236-264 (translated)
3. **Repository Structure** — Full tree showing domain/, adapters/, entities/, api/, profiles/, platform files
4. **Domain Layer** (`domain/`)
   - Responsibility: Pure business logic, zero HA dependencies
   - Structure: models/ (data), ports/ (interfaces), services/ (logic)
   - Strict rules: NEVER import homeassistant.*, NEVER import adapters/entities, stdlib only, use Protocols
   - Key services list: COP, thermal, timing, electrical, defrost guard
   - Link to `docs/reference/domain-services.md` for details
5. **Adapters Layer** (`adapters/`)
   - Responsibility: Implements domain ports, bridges domain with HA
   - Structure: calculators/, providers/, storage/
   - Patterns: Adapter, Strategy, Dependency Injection
   - Rules: always implement ports, delegate to domain, handle HA errors
6. **Entity Layer** (`entities/`)
   - Responsibility: Domain-driven HA entity organization
   - Structure: one folder per business domain (11 domains)
   - Builder pattern: each domain exports `build_<domain>_<entity_type>()` functions
   - Base classes in `entities/base/`
   - Platform files (`sensor.py`, etc.) are thin orchestrators calling builders
   - Link to `docs/reference/entity-patterns.md` for patterns
7. **Platform Layer** — Entry points for HA (`sensor.py`, `climate.py`, etc.)
   - Responsibility: `async_setup_entry()` calls builders and registers entities
8. **API Layer** (`api/`) — Modbus communication
   - Link to `docs/development/modbus-registers.md`
9. **Data Flow** — Modbus → API client → Coordinator cache → Domain services → Entities → HA state
10. **Domain-to-Entity-Type Matrix** — table from `documentation/architecture.md` lines 200-211 (translated)

Content sources and what to take from each:
- From `documentation/architecture.md`: Overall structure, layer diagram, domain matrix, domain responsibilities table
- From `domain/README.md`: Models/Ports/Services inventory, strict rules, usage examples
- From `adapters/README.md`: Adapter categories, patterns, extension examples
- From `entities/README.md`: Module descriptions, creation pattern, domain integration example
- From CLAUDE.md: Layer rules (NEVER/ALWAYS), data flow description

Target length: ~250 lines. Translate all French content to English. Remove migration status (obsolete), remove emoji decorations.

**Step 2: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: add unified architecture document"
```

---

### Task 3: Write docs/reference/entity-patterns.md

Translate and adapt `documentation/entities.md` (French, 299 lines).

**Files:**
- Create: `docs/reference/entity-patterns.md`

**Step 1: Write the document**

Structure:
1. **Overview** — Link back to `docs/architecture.md` for the big picture
2. **Configuration Pattern** — Entity descriptions as dataclasses (from entities.md section 2)
3. **Builder Pattern** — Dynamic description construction (section 3)
4. **Factory Pattern** — Centralized entity creation via `_create_*()` (section 6)
5. **Conditional Creation** — Dynamic filtering based on device capabilities (section 7)
6. **Unique ID Strategy** — `{entry_id}_{key}` or `{entry_id}_{prefix}_{key}` (section 9)
7. **Device Assignment** — Constants for device IDs, common pitfall with dynamic strings (section 10)
8. **Domain Structure** — Standard file layout for a domain folder (`__init__.py`, `sensors.py`, etc.)
9. **Base Classes Reference** — Table of all base classes in `entities/base/` with their description classes and factory functions
10. **Adding an Entity to an Existing Domain** — Quick reference steps
11. **Creating a New Domain** — Quick reference steps

Translate all French to English. Keep code examples. Remove emoji decorations. Remove "Avantages" lists (they're marketing, not reference). Remove SRP and DIP sections (too abstract, not actionable).

Target length: ~200 lines.

**Step 2: Commit**

```bash
git add docs/reference/entity-patterns.md
git commit -m "docs: add entity patterns reference"
```

---

### Task 4: Move and clean up quality-scale.md

**Files:**
- Move: `documentation/quality-scale-assessment.md` → `docs/reference/quality-scale.md`

**Step 1: Move file**

```bash
git mv documentation/quality-scale-assessment.md docs/reference/quality-scale.md
```

**Step 2: Clean up content**

- Fix the missing accents (the file has no accents: "concu", "classees", "scorees" etc.) — this is a known charset issue, fix them
- Update version reference from `2.0.0-beta.12` to current
- Remove French notes, translate to English

**Step 3: Commit**

```bash
git add docs/reference/quality-scale.md
git commit -m "docs: move quality scale assessment to docs/reference/"
```

---

### Task 5: Write docs/reference/domain-services.md

New document based on domain service code exploration.

**Files:**
- Create: `docs/reference/domain-services.md`

**Step 1: Write the document**

Structure:
1. **Overview** — Domain services contain pure business logic with zero HA dependencies. All are testable without mocks.
2. **COP Calculation** (`domain/services/cop.py`)
   - Purpose: Monitor efficiency via thermal/electrical energy ratio
   - Key classes: `COPService`, `EnergyAccumulator`
   - Input model: `COPInput` (water temps, flow, compressor data, operation mode)
   - Quality thresholds: no_data (0), insufficient_data (<5 measurements OR <5min), preliminary (5-14/5-14min), optimal (>=15/>=15min)
   - Uses: `ThermalPowerCalculator` and `ElectricalPowerCalculator` ports
3. **Thermal Energy** (`domain/services/thermal/`)
   - Purpose: Track heating and cooling energy separately
   - Key classes: `ThermalPowerService`, `ThermalEnergyAccumulator`
   - Heating vs cooling: ΔT > 0 → heating, ΔT < 0 → cooling
   - DHW/Pool: always counted as heating regardless of ΔT
   - Post-cycle lock: filters thermal inertia after compressor stops
   - Daily reset at midnight, total energy persistent
   - Formula: Q = flow_kg/s × 4.185 × ΔT
4. **Defrost Guard** (`domain/services/defrost_guard.py`)
   - Purpose: Filter unreliable data during defrost cycles
   - State machine: NORMAL → DEFROST → RECOVERY → NORMAL
   - Recovery exits after 3 stable readings or 5min timeout
   - `is_data_reliable` property used upstream by COP/thermal
5. **Compressor Timing** (`domain/services/timing.py`)
   - Purpose: Track cycle time, runtime, rest time
   - Key classes: `CompressorTimingService`, `CompressorHistory`
   - Output: `CompressorTimingResult` (cycle_time_min, runtime_min, resttime_min)
6. **Electrical Power** (`domain/services/electrical.py`)
   - Purpose: Calculate electrical consumption
   - Priority: measured_power > voltage×current > default voltage
   - Formulas: 3-phase `P = U × I × 0.9 × √3 / 1000`, single-phase `P = U × I × 0.9 / 1000`
7. **Ports** (`domain/ports/`)
   - `ThermalPowerCalculator`: callable(inlet, outlet, flow) → float
   - `ElectricalPowerCalculator`: callable(current) → float
   - `DataProvider`: water temps, flow, compressor data
   - `StateProvider`: get_float_from_entity()
   - `Storage[T]`: append, popleft, get_all, len
8. **Integration diagram** — ASCII showing Domain → Adapters → Entities data flow

Target length: ~200 lines.

**Step 2: Commit**

```bash
git add docs/reference/domain-services.md
git commit -m "docs: add domain services reference"
```

---

### Task 6: Write docs/development/getting-started.md

New document combining content from README.md (dev section) and CONTRIBUTING.md.

**Files:**
- Create: `docs/development/getting-started.md`

**Step 1: Write the document**

Structure:
1. **Prerequisites** — Python 3.12+, uv, git
2. **Setup**
   - Fork + clone
   - `make setup` (installs deps + pre-commit hooks)
   - Verify: `make check && make test`
3. **Running Home Assistant locally**
   - `make ha-run` → http://localhost:8123
   - Custom port via `config/configuration.yaml`
   - Dev container option (VS Code + Dev Containers extension)
4. **Project structure overview** — Simplified tree with one-line descriptions per directory (point to `docs/architecture.md` for details)
5. **Make targets reference** — Full table from README.md lines 539-556
6. **Running tests**
   - `make test` — all tests
   - `make test-domain` — domain layer only (fast, no HA)
   - `make test-coverage` — with coverage report
7. **Code quality**
   - Ruff handles lint + format (see `.ruff.toml`)
   - Pre-commit hooks run automatically
   - `make check` before committing
8. **Your first contribution**
   - Branch from `dev`: `git checkout -b feat/my-feature`
   - Make changes following architecture rules
   - Update `CHANGELOG.md` under `[Unreleased]`
   - Run `make check && make test`
   - Commit with conventional commit format
   - Open PR targeting `dev`
9. **Useful links** — Pointers to architecture.md, adding-entities.md, modbus-registers.md, profiles.md

Sources: README.md lines 496-557, CONTRIBUTING.md full content.

Target length: ~150 lines.

**Step 2: Commit**

```bash
git add docs/development/getting-started.md
git commit -m "docs: add getting started development guide"
```

---

### Task 7: Write docs/development/adding-entities.md

New step-by-step guide based on entity patterns and CLAUDE.md.

**Files:**
- Create: `docs/development/adding-entities.md`

**Step 1: Write the document**

Structure:
1. **Overview** — Entities are organized by business domain, not by HA entity type. Links to architecture.md and entity-patterns.md.
2. **Adding an entity to an existing domain** — Step-by-step:
   a. Identify the business domain (gateway, circuit, dhw, etc.)
   b. Open the appropriate file (`entities/<domain>/sensors.py`, `switches.py`, etc.)
   c. Add a description to the `_build_<domain>_<type>_descriptions()` function
   d. Add translation key to `translations/en.json`
   e. If conditional, add a `condition` lambda
   f. Run `make test && make ha-run` to verify
   g. Example: adding a new sensor to `control_unit`
3. **Creating a new domain** — Step-by-step:
   a. Create `entities/<new_domain>/` directory
   b. Create `__init__.py` with builder exports
   c. Create entity type files (`sensors.py`, etc.) with builder functions
   d. Update platform orchestrator (`sensor.py`, etc.) to import and call builder
   e. Add translations
   f. Example: creating a hypothetical `ventilation` domain
4. **Common pitfalls**
   - Using dynamic strings for device IDs instead of constants
   - Putting business logic in entity classes
   - Importing HA modules in domain layer
   - Forgetting to add conditions for optional features
5. **Checklist** — Quick checklist for adding entities

Sources: CLAUDE.md "When Adding New Entities", `documentation/entities.md` contribution guide, `entities/README.md` "Adding New Entities".

Target length: ~150 lines.

**Step 2: Commit**

```bash
git add docs/development/adding-entities.md
git commit -m "docs: add entity creation development guide"
```

---

### Task 8: Write docs/development/modbus-registers.md

New guide based on code exploration of the register system.

**Files:**
- Create: `docs/development/modbus-registers.md`

**Step 1: Write the document**

Structure:
1. **Overview** — Registers are the interface between integration and heat pump hardware. Each gateway type has its own register map.
2. **Key concepts**
   - Register vs Key: Modbus address (1091) vs human-readable key (`"outdoor_temp"`)
   - CONTROL vs STATUS: R/W commands vs R actual state. **Always read from STATUS registers** for sensor entities.
   - RegisterDefinition: address, deserializer, serializer, write_address, fallback
3. **Register definition files**
   - `api/modbus/registers/atw_mbs_02.py` — ATW-MBS-02 gateway
   - `api/modbus/registers/hc_a_mb.py` — HC-A(16/64)MB gateway
   - Registers grouped by device: REGISTER_GATEWAY, REGISTER_CONTROL_UNIT, REGISTER_CIRCUIT_1, etc.
4. **Common deserializers**
   - `convert_signed_16bit()` — 2's complement for negative values
   - `convert_from_tenths()` — divide by 10 (500 → 50.0°C)
   - `convert_pressure()` — divide by 10 for MPa → bar
   - `deserialize_unit_model()` — numeric → string mapping
   - `deserialize_system_state()` — numeric → state string
5. **Data flow**
   - Gateway → `api_client.read_values(keys)` → `coordinator.data[key]` → `entity.value_fn(coordinator)`
   - For writes: entity → `api_client.write_value(key, value)` → serializer → Modbus write
6. **Adding a new register** — Step-by-step:
   a. Identify the register address from gateway documentation (see `docs/gateway/`)
   b. Add `RegisterDefinition` to appropriate `REGISTER_*` dict
   c. Add deserializer if raw value needs conversion
   d. If writable: add serializer and to `WRITABLE_KEYS`
   e. Create entity description referencing the key
   f. If model-specific: add to profile's `extra_register_keys`
   g. Example: adding a read-only temperature register
   h. Example: adding a writable control register
7. **Sentinel values** — Table of error codes (0xFFFF, 0xFF81, 0xFFBD)
8. **Gateway documentation** — Links to `docs/gateway/atw-mbs-02.md`, `hc-a-mb.md`, `scan-reference.md`

Target length: ~180 lines.

**Step 2: Commit**

```bash
git add docs/development/modbus-registers.md
git commit -m "docs: add Modbus registers development guide"
```

---

### Task 9: Write docs/development/profiles.md

New guide based on profile system code exploration.

**Files:**
- Create: `docs/development/profiles.md`

**Step 1: Write the document**

Structure:
1. **Overview** — Profiles define heat pump model capabilities. Auto-detected during config flow.
2. **How detection works**
   - Config flow reads Modbus registers → decodes to dict
   - Each profile's `detect()` method checks the data
   - First match wins; user selects if ambiguous
3. **Base class** (`profiles/base.py`)
   - Abstract: `detect(data)`, `name`
   - DHW: `supports_dhw`, `dhw_min_temp`, `dhw_max_temp`, `antilegionella_min_temp`, `antilegionella_max_temp`
   - Circuits: `max_circuits`, `supports_circuit1`, `supports_circuit2`, `supports_cooling`, `max_water_outlet_temp`
   - Special: `supports_high_temperature`, `supports_secondary_compressor`, `supports_boiler`, `supports_pool`
   - Extensions: `extra_register_keys`, `entity_overrides`
4. **Current profiles** — Table of 7 models with key features
5. **Adding a new profile** — Step-by-step:
   a. Create `profiles/your_model.py` inheriting from `HitachiHeatPumpProfile`
   b. Implement `detect()` and `name`
   c. Override capability properties as needed
   d. Register in `profiles/__init__.py` PROFILES dict
   e. Add model detection mapping in register deserializer if new ID
   f. Add `extra_register_keys` if model has unique registers
   g. Add `entity_overrides` if model needs entity config tweaks
   h. Test detection logic

Target length: ~150 lines.

**Step 2: Commit**

```bash
git add docs/development/profiles.md
git commit -m "docs: add heat pump profiles development guide"
```

---

### Task 10: Rewrite CLAUDE.md

Slim from ~305 lines to ~150-180 lines. Remove explanations, keep rules and conventions only.

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Rewrite the file**

**Keep (with edits):**
- Project Overview — shorten to 3-4 lines, add `docs/` pointer
- Development Commands — keep as-is
- Architecture section — **remove** Layer Structure tree and Entity Builder Pattern code examples. Keep only Critical Architecture Rules (NEVER/ALWAYS). Add pointer to `docs/architecture.md`
- Key Domain Concepts — shorten each to 1-2 bullet points max, add pointers to `docs/reference/domain-services.md`
- Important Development Notes — replace "When Adding New Entities" and "When Modifying Calculations" with pointers to `docs/development/adding-entities.md` and `docs/reference/domain-services.md`
- Modbus Register Access — shorten to essential rule (always read STATUS), add pointer to `docs/development/modbus-registers.md`
- Circuit Climate Architecture — **keep fully** (it's a critical trap)
- Entity Migration — keep (historical context)
- Translations — keep (short, normative)
- Code Quality Standards — keep
- Testing — keep
- Dependencies — keep but shorten
- Branch Strategy — keep
- Git Conventions — keep
- Version Management — keep

**Remove entirely:**
- Layer Structure tree (→ `docs/architecture.md`)
- Entity Builder Pattern examples (→ `docs/reference/entity-patterns.md`)
- Common Patterns section (→ `docs/development/` and `docs/reference/`)
- Documentation section (self-evident with new structure)
- Devices Created list (→ README.md already has it)

**Add:**
- Documentation section pointing to `docs/` structure

**Step 2: Verify line count**

Target: ~150-180 lines.

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: slim CLAUDE.md to rules and conventions only"
```

---

### Task 11: Rewrite CONTRIBUTING.md

Slim down, point to `docs/development/getting-started.md` for details.

**Files:**
- Modify: `CONTRIBUTING.md`

**Step 1: Rewrite the file**

Structure:
1. **Quick Start** — Fork, clone, `make setup`, `make check && make test`
2. **Development Guide** — Pointer to `docs/development/getting-started.md`
3. **Branch Strategy** — Keep table (main/dev/feature) and release flow
4. **Pull Requests** — Keep PR guidelines (base=dev, squash merge, CI checks)
5. **Changelog** — Keep format reference
6. **Translations** — Keep Weblate reference
7. **Code Style** — Keep ruff reference
8. **Architecture** — One sentence + pointer to `docs/architecture.md`

Remove: Make targets table (moved to getting-started.md), detailed "Making Changes" section (redundant with getting-started.md).

Target: ~80 lines.

**Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: slim CONTRIBUTING.md, point to docs/development/"
```

---

### Task 12: Update README.md

Fix internal links to point to new `docs/` paths. No structural rewrite.

**Files:**
- Modify: `README.md`

**Step 1: Update links**

Replace:
- `custom_components/hitachi_yutaki/domain/README.md` → `docs/architecture.md`
- `custom_components/hitachi_yutaki/adapters/README.md` → `docs/architecture.md`
- `custom_components/hitachi_yutaki/entities/README.md` → `docs/architecture.md`
- `documentation/` references → `docs/`
- Remove the "Architecture Documentation" subsection (lines 428-433) that links to deleted layer READMEs — replace with single link to `docs/architecture.md`
- Update project structure tree (line 493): `documentation/` → `docs/`

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README.md links to new docs/ structure"
```

---

### Task 13: Create GitHub templates

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/pull_request_template.md`

**Step 1: Create bug report template**

`.github/ISSUE_TEMPLATE/bug_report.yml`:
- Name: Bug Report
- Fields:
  - Description (textarea, required)
  - Steps to reproduce (textarea, required)
  - Expected behavior (textarea, required)
  - Home Assistant version (input, required)
  - Integration version (input, required)
  - Heat pump model (dropdown: Yutaki S / S Combi / S80 / M / Yutampo R32 / SC Lite / Other, required)
  - Gateway type (dropdown: ATW-MBS-02 / HC-A16MB / HC-A64MB / Other, required)
  - Relevant logs (textarea, optional, render as shell)
  - Additional context (textarea, optional)

**Step 2: Create feature request template**

`.github/ISSUE_TEMPLATE/feature_request.yml`:
- Name: Feature Request
- Fields:
  - Description (textarea, required)
  - Use case (textarea, required)
  - Affected model (dropdown: same list + All / Not sure, optional)
  - Additional context (textarea, optional)

**Step 3: Create PR template**

`.github/pull_request_template.md`:
```markdown
## Description

<!-- What does this PR do? Why? -->

## Checklist

- [ ] Tests pass (`make test`)
- [ ] Code quality checks pass (`make check`)
- [ ] `CHANGELOG.md` updated under `[Unreleased]` (or `skip-changelog` label added)
- [ ] New/modified entities follow [architecture rules](docs/architecture.md)
- [ ] Translation keys added to `translations/en.json` (if applicable)
```

**Step 4: Commit**

```bash
git add .github/ISSUE_TEMPLATE/ .github/pull_request_template.md
git commit -m "docs: add GitHub issue and PR templates"
```

---

### Task 14: Delete old files and clean up

**Files:**
- Delete: `documentation/architecture.md`
- Delete: `documentation/entities.md`
- Delete: `documentation/gateway/` (empty after moves)
- Delete: `documentation/pac/` (empty after moves)
- Delete: `documentation/` (should be empty)
- Delete: `custom_components/hitachi_yutaki/domain/README.md`
- Delete: `custom_components/hitachi_yutaki/adapters/README.md`
- Delete: `custom_components/hitachi_yutaki/entities/README.md`
- Delete: `TODO-hc-a-mb-registers.md` (content already in `docs/gateway/hc-a-mb.md` and a GitHub issue should be created)

**Step 1: Delete old documentation files**

```bash
git rm documentation/architecture.md
git rm documentation/entities.md
git rm -r documentation/gateway/ documentation/pac/
rmdir documentation 2>/dev/null  # Remove if empty
git rm documentation/.DS_Store 2>/dev/null  # Clean up macOS artifacts
```

**Step 2: Delete in-code READMEs**

```bash
git rm custom_components/hitachi_yutaki/domain/README.md
git rm custom_components/hitachi_yutaki/adapters/README.md
git rm custom_components/hitachi_yutaki/entities/README.md
```

**Step 3: Delete root TODO**

```bash
git rm TODO-hc-a-mb-registers.md
```

**Step 4: Verify nothing is left behind**

```bash
# Should return nothing in documentation/
find documentation/ -type f 2>/dev/null
# Should return no README.md in domain/, adapters/, entities/
ls custom_components/hitachi_yutaki/{domain,adapters,entities}/README.md 2>/dev/null
```

**Step 5: Commit**

```bash
git add -A
git commit -m "docs: remove old documentation files and in-code READMEs"
```

---

### Task 15: Update CHANGELOG.md

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Add entry under [Unreleased]**

```markdown
### Changed
- Restructured documentation: unified `docs/` directory, English-only, centralized architecture docs
- Slimmed `CLAUDE.md` to rules and conventions only (details moved to `docs/`)
- Slimmed `CONTRIBUTING.md` with pointers to `docs/development/`

### Added
- `docs/architecture.md`: unified architecture reference (merged 5 sources)
- `docs/development/`: getting started, adding entities, Modbus registers, profiles guides
- `docs/reference/`: entity patterns, domain services, quality scale references
- GitHub issue templates (bug report, feature request) and PR template
```

**Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG.md with documentation restructure"
```

---

### Task 16: Final verification

**Step 1: Check all internal links resolve**

```bash
# Find all markdown links and verify targets exist
grep -roh '\[.*\]([^)]*\.md[^)]*)' docs/ CLAUDE.md CONTRIBUTING.md README.md | \
  grep -oP '\(([^)]+)\)' | tr -d '()' | sort -u
```

Manually verify each link resolves to an existing file.

**Step 2: Run lint**

```bash
make check
```

**Step 3: Run tests**

```bash
make test
```

Tests should pass unchanged — this is a docs-only change.

**Step 4: Review final file count**

```bash
# New docs/ structure
find docs/ -type f | sort

# Verify old files are gone
ls documentation/ 2>/dev/null
ls custom_components/hitachi_yutaki/{domain,adapters,entities}/README.md 2>/dev/null
ls TODO-hc-a-mb-registers.md 2>/dev/null
```

**Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "docs: fix any remaining issues from documentation restructure"
```

---

## Task Dependencies

Tasks 1-9 can mostly be parallelized (independent file creation). However:
- Task 10 (CLAUDE.md rewrite) should happen after Tasks 2-9 are done, so pointers are accurate
- Task 12 (README.md) should happen after Task 14 (deletions), so old paths don't exist
- Task 14 (deletions) must happen after Tasks 1-4 (moves/merges are done)
- Task 15 (CHANGELOG) should be last content change
- Task 16 (verification) must be truly last

Recommended execution order:
1. Task 1 (directory structure + gateway moves)
2. Tasks 2-9 in parallel (all new docs)
3. Tasks 10-11 (rewrite root files)
4. Task 12 (update README links)
5. Task 13 (GitHub templates)
6. Task 14 (delete old files)
7. Task 15 (CHANGELOG)
8. Task 16 (verification)
