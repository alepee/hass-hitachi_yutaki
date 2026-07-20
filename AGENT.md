# AGENT.md: agent & contributor guide

Canonical, tool-agnostic guidance for any AI coding agent (Claude Code, Codex, Cursor, Aider, …) or human contributor working in this repository. Tool-specific entrypoints (`CLAUDE.md`, editor configs) should defer to this file rather than duplicate it.

## Project Overview

Home Assistant custom integration for Hitachi air-to-water heat pumps (Yutaki and Yutampo models). Communicates via Modbus with ATW-MBS-02 and HC-A(16/64)MB gateways. Follows hexagonal architecture. The version source of truth is `manifest.json`. See [`docs/`](docs/) for detailed documentation.

## Development Commands

All commands are available as `make` targets. Run `make help` to list them.

```bash
make setup           # Full project setup (deps + pre-commit hooks)
make install         # Install/reinstall all dependencies
make check           # Run all code quality checks (lint + format)
make lint            # Run ruff linter with auto-fix
make test            # Run all tests
make test-domain     # Run domain layer tests only (pure Python, no HA)
make test-coverage   # Run tests with coverage report
make ha-run          # Start a local HA dev instance with debug config
make bump            # Bump version (patch by default)
make bump PART=minor # Bump minor version (e.g., 2.0.2 → 2.1.0)
make bump PART=major # Bump major version (e.g., 2.1.0 → 3.0.0)
```

Pre-commit hooks are installed by `make setup` and run ruff on every commit.

## Architecture

This integration follows **Hexagonal Architecture** (Ports and Adapters) with strict separation of concerns. See [docs/architecture.md](docs/architecture.md) for the full picture.

### Critical Architecture Rules

**Domain Layer** (`domain/`):
- **NEVER** import `homeassistant.*`
- **NEVER** import from `adapters.*` or `entities.*`
- **NEVER** use external libraries (stdlib only)
- **ALWAYS** use Protocols for dependencies
- Pure business logic that can be tested without HA mocks

**Adapters Layer** (`adapters/`):
- Implements domain ports/protocols
- Bridges domain with Home Assistant infrastructure
- Delegates business logic to domain services
- Handles HA-specific concerns (state retrieval, entity data)

**Entity Layer** (`entities/`):
- Organized by **business domain** (not by entity type)
- Each domain has builder functions that return entity lists
- Uses base classes from `entities/base/` for common HA entity patterns
- Platform files (`sensor.py`, etc.) call builders and register entities

## Key Domain Concepts

See [docs/reference/domain-services.md](docs/reference/domain-services.md) for detailed service documentation.

### Heat Pump Profiles
- Auto-detected from Modbus data; a profile declares capabilities (DHW, pool, circuits, compressors, water circuit, extended compressor sensors) and temperature ranges.
- Base class: `HitachiHeatPumpProfile` (`profiles/base.py`); models register in `profiles/__init__.py` (`PROFILES`).
- Capability flags gate entity creation (via `condition` callbacks), e.g. a DHW-only Yutampo R32 sets `supports_water_circuit=False` and `supports_extended_compressor_sensors=False`.

### COP Calculation
- Coefficient of Performance monitoring using energy accumulation over time.
- Quality levels: `no_data`, `insufficient_data`, `preliminary`, `optimal` (`domain/services/cop.py`).

### Thermal Energy Tracking
- Separate tracking for heating and cooling (real-time power, daily energy, total energy).
- **Defrost filtering** and **post-cycle lock** prevent measurement noise.

### Anonymous Telemetry
- Binary consent (Off / On) stored in `entry.options["telemetry_level"]` (`CONF_TELEMETRY_LEVEL`, default `"off"`).
- **Package** (`telemetry/`): models (three payloads: `InstallationInfo`, `MetricsBatch`, `RegisterSnapshot`), collector (circular buffer), anonymizer (SHA-256 hash, temperature/geolocation rounding), HTTP client (gzip + retry), noop client.
- **Coordinator wiring**: collect on each poll, 5-min metrics flush, one-time installation info + register snapshot on first successful poll (fire-and-forget with `asyncio.Lock` + exponential backoff), and a daily re-send of the installation payload at the UTC day boundary (keeps WAE's 90-day window populated). There is no separate daily-stats aggregator.
- **Backend**: Cloudflare Worker (ingestion/validation/rate-limit per payload type) → R2 (permanent JSON archive, partitioned Hive-style). Installation payloads are mirrored to Workers Analytics Engine (dataset `hitachi_installations`) for a Grafana fleet dashboard; the integration re-sends installation daily to keep WAE's 90-day window populated.
- **Consent flows**: options flow step (after sensors), repair flow for existing users.
- **Diagnostic entity**: `sensor.telemetry_status` (ENUM off/on) with attributes (`points_buffered`, `last_send`, `send_failures`).
- To build a local test dataset from the archive, see [docs/development/telemetry-dataset.md](docs/development/telemetry-dataset.md).
- See [docs/reference/telemetry.md](docs/reference/telemetry.md).

### Devices Created
- **Gateway**, **Control Unit**, **Primary Compressor** (always present).
- **Secondary Compressor** (S80 only), **Circuit 1 & 2**, **DHW**, **Pool** (created when the profile/`system_config` declares them).

## Important Development Notes

### When Adding New Entities
Follow the domain builder pattern. See [docs/development/adding-entities.md](docs/development/adding-entities.md). **Never** add business logic to entity classes; gate optional entities with a `condition` callback on the entity description.

### When Modifying Calculations
Domain logic goes in `domain/services/`, adapter logic in `adapters/`. See [docs/reference/domain-services.md](docs/reference/domain-services.md). The domain layer must remain HA-agnostic.

### Modbus Register Access
**Always read from STATUS registers** for sensor entities: CONTROL registers only reflect what was commanded, not the actual running state. Register definitions carry both a read (STATUS) address and a `write_address` (CONTROL). See [docs/development/api-data-keys.md](docs/development/api-data-keys.md).

### Circuit Climate Architecture
- **Operating mode is global**: the `unit_mode` register (STATUS `1051` / CONTROL `1001` on the 2016 map) controls heat/cool/auto for **all** circuits at once.
- **Circuit power is per-circuit**: `circuit1_power` (STATUS `1052` / CONTROL `1002`) and `circuit2_power` (STATUS `1064` / CONTROL `1013`) toggle each circuit independently. (Addresses differ on the pre-2016 map; reference the register keys, not raw numbers.)
- **Single circuit active**: the climate entity exposes `off`/`heat`/`cool`/`auto` and controls both power and global mode.
- **Two circuits active**: climate entities expose only `off`/`heat_cool` (power toggle); the global mode is controlled exclusively via the control-unit operating-mode select (`operation_mode_heat` or `operation_mode_full`, per `entities/control_unit/selects.py`) to avoid side-effects between circuits.

### When Modifying Telemetry
- **Integration side**: models/collector in `telemetry/`, wiring in `coordinator.py`, consent in `config_flow.py` + `repairs.py`.
- **Backend side**: Cloudflare Worker in `backend/worker/src/`.
- Fields must match across Python models (`to_dict()`) and the Worker validator (field whitelists).
- Telemetry entities read from coordinator attributes (not `coordinator.data`).
- Deploy Worker changes with `cd backend/worker && npx wrangler deploy`.

### Entity Migration
- `entity_migration.py` handles `unique_id` migrations; it runs automatically during integration setup.

### Translations
- **Source of truth**: `translations/en.json` is edited by developers in the repo.
- **Other languages**: edited directly in the JSON files or via [Weblate](https://hosted.weblate.org/engage/hass-hitachi_yutaki/) (two-way sync). When editing a JSON file also touched on Weblate, check for conflicts on the same keys.

## Code Quality Standards
- **Linting**: Ruff with the Home Assistant ruleset (configured in `pyproject.toml` under `[tool.ruff]`).
- **Type hints**: required for all function signatures.
- **Docstrings**: required for all public functions/classes.
- **Import conventions**: use the aliases from `[tool.ruff.lint.flake8-import-conventions.extend-aliases]` in `pyproject.toml` (e.g., `vol`, `cv`, `dt_util`).

## Testing
Tests live in `tests/` (mirrors the package layout):
- `tests/domain/`: domain-layer unit tests (pure Python, no HA).
- `tests/entities/`, `tests/adapters/`, `tests/api/`, `tests/profiles/`: layer-specific tests.
- `tests/test_telemetry_*.py`: telemetry unit + integration tests.
- Uses `pytest` and `pytest-asyncio`. Run with `make test`.

## Dependencies
All dependencies are declared in `pyproject.toml` (single source of truth).
- **Runtime**: `pymodbus`, Home Assistant core.
- **Dev**: `pytest-homeassistant-custom-component`, `ruff`, `pre-commit`, `pytest`, `pytest-asyncio`.

## Operating Modes (preserved conventions)

These workflows are stable; do not change them without explicit request. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow.

### Branch Strategy
- **`main`**: single branch, all development and releases happen here.
- **Feature branches**: created from `main`, named `feat/...`, `fix/...`, or `chore/...`.
- **PRs to `main`**: squash-merged (one commit per PR).

### Git Conventions
- **No AI signature**: do not add "Co-Authored-By: …" trailers in commit messages.
- Use conventional-commit style (`fix:`, `feat:`, `docs:`, `chore:`, `test:`, `release:`) when appropriate.
- **Changelog**: every behavior-affecting PR must add an entry under `[Unreleased]` in `CHANGELOG.md` (Keep a Changelog format). PRs with no user-facing effect may use the `skip-changelog` label.

### Version Management
Version lives in two files, kept in sync by `make bump`:
- `manifest.json` → `"version"`: **source of truth** (read by HA core + HACS at runtime).
- `pyproject.toml` → `version`: metadata only (build tools).

Use `make bump [PART=minor|major]` to increment and update both files.

### Release Process
Release flow: `make bump` on `main` → commit → push → create a GitHub release with the tag. **When drafting a release, follow the release template so the title and description stay consistent with past releases**: [docs/development/release-template.md](docs/development/release-template.md).

## Keeping Documentation in Sync

Documentation is part of the definition of done: treat it like tests. This replaces any external doc-sync tooling with a plain, tool-agnostic convention.

**Rule**: a PR that changes behavior, architecture, registers, entities, or a public workflow **must** update the affected docs in the same PR. Do not assume a doc is correct; verify statements against the code before relying on or copying them.

Code-area → doc-file map (update the right doc when you touch that area):

| You changed… | Update… |
|---|---|
| Layers, data flow, import rules | [docs/architecture.md](docs/architecture.md), this file |
| A domain service / calculation | [docs/reference/domain-services.md](docs/reference/domain-services.md) |
| Entity builders / new entity | [docs/development/adding-entities.md](docs/development/adding-entities.md), [docs/reference/entities.md](docs/reference/entities.md), [docs/reference/entity-patterns.md](docs/reference/entity-patterns.md) |
| A profile / capability flag | [docs/development/profiles.md](docs/development/profiles.md), [docs/reference/model-nomenclature.md](docs/reference/model-nomenclature.md) |
| Registers / gateway map / data keys | [docs/development/api-data-keys.md](docs/development/api-data-keys.md), [docs/gateway/](docs/gateway/) |
| Telemetry (integration or backend) | [docs/reference/telemetry.md](docs/reference/telemetry.md), [docs/development/telemetry-dataset.md](docs/development/telemetry-dataset.md) |
| Commands, conventions, operating modes | this file, [CONTRIBUTING.md](CONTRIBUTING.md) |

The PR checklist ([.github/pull_request_template.md](.github/pull_request_template.md)) restates this so it is enforced at review time.

## Documentation Index
- [Architecture](docs/architecture.md): hexagonal layers, data flow, domain matrix.
- [Development guides](docs/development/): getting started, adding entities, registers/data keys, profiles, telemetry dataset.
- [Reference](docs/reference/): entity reference, entity patterns, domain services, quality scale, telemetry, model nomenclature.
- [Gateway docs](docs/gateway/): register maps, scan reference, sentinel values, datasheets.
- [Troubleshooting](docs/troubleshooting.md).
