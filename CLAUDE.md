# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant custom integration for Hitachi air-to-water heat pumps (Yutaki and Yutampo models). Communicates via Modbus with ATW-MBS-02 and HC-A(16/64)MB gateways. Follows hexagonal architecture. Version is in `manifest.json`. See [`docs/`](docs/) for detailed documentation.

## Development Commands

All commands are available as `make` targets. Run `make help` to list them.

```bash
make setup          # Full project setup (deps + pre-commit hooks)
make install        # Install/reinstall all dependencies
make check          # Run all code quality checks (lint + format)
make lint           # Run ruff linter with auto-fix
make test           # Run all tests
make test-domain    # Run domain layer tests only (pure Python, no HA)
make test-coverage  # Run tests with coverage report
make ha-run         # Start a local HA dev instance with debug config
make bump           # Bump version (patch by default)
make bump PART=minor # Bump minor version (e.g., 2.0.2 → 2.1.0)
make bump PART=major # Bump major version (e.g., 2.1.0 → 3.0.0)
```

Pre-commit hooks are automatically installed by `make setup` and run ruff on every commit.

## Architecture

This integration follows **Hexagonal Architecture** (Ports and Adapters) with strict separation of concerns. See [docs/architecture.md](docs/architecture.md) for full architecture documentation.

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
- Auto-detected based on Modbus data; defines capabilities (DHW, pool, circuits, compressors)
- Base class: `HitachiHeatPumpProfile` with detection logic

### COP Calculation
- Coefficient of Performance monitoring using energy accumulation over time
- Quality levels: `no_data`, `insufficient_data`, `preliminary`, `optimal`

### Thermal Energy Tracking
- Separate tracking for heating and cooling (real-time power, daily energy, total energy)
- **Defrost filtering** and **post-cycle lock** prevent measurement noise

### Devices Created
- **Gateway**, **Control Unit**, **Primary Compressor** (always present)
- **Secondary Compressor** (S80 only), **Circuit 1 & 2**, **DHW**, **Pool** (if configured)

## Important Development Notes

### When Adding New Entities

Follow the domain builder pattern. See [docs/development/adding-entities.md](docs/development/adding-entities.md) for the step-by-step guide. **Never** add business logic to entity classes.

### When Modifying Calculations

Domain logic goes in `domain/services/`, adapter logic in `adapters/calculators/`. See [docs/reference/domain-services.md](docs/reference/domain-services.md). Domain layer must remain HA-agnostic.

### Modbus Register Access

**Always read from STATUS registers** for sensor entities -- CONTROL registers only reflect what was commanded, not the actual running state. See [API Layer & Data Keys](docs/development/api-data-keys.md) for details.

### Circuit Climate Architecture
- **Operating mode is global**: register 1001 (`unit_mode`) controls heat/cool/auto for **all** circuits simultaneously
- **Circuit power is per-circuit**: registers 1002 (circuit 1) and 1013 (circuit 2) toggle each circuit independently
- **Single circuit active**: climate entity exposes `off`/`heat`/`cool`/`auto` and controls both power and global mode
- **Two circuits active**: climate entities expose only `off`/`heat_cool` (power toggle only) -- global mode is controlled exclusively via the `control_unit_operation_mode` select entity to avoid unintended side-effects between circuits

### Entity Migration (v2.0.0)
- `entity_migration.py` handles unique_id migrations for beta users
- Runs automatically during integration setup
- Migration tracking in `2.0.0_entity_migration*.md` files

### Translations

- **Source of truth**: `en.json` is edited by developers in the repo
- **Other languages**: edited directly in JSON files or contributed via [Weblate](https://hosted.weblate.org/engage/hass-hitachi_yutaki/)
- **Weblate**: external contributors can translate without coding -- changes sync both ways. If editing a JSON file that was also modified on Weblate, check for conflicts on the same keys

## Code Quality Standards

- **Linting**: Ruff with Home Assistant ruleset (see `.ruff.toml`)
- **Type hints**: Required for all function signatures
- **Docstrings**: Required for all public functions/classes
- **Line length**: Enforced by formatter, not limited
- **Import conventions**: Use aliases from `.ruff.toml` (e.g., `vol`, `cv`, `dt_util`)

## Testing

Tests are in `tests/` directory:
- `tests/domain/`: Domain layer unit tests (pure Python, no HA)
- Test files use `pytest` and `pytest-asyncio`

Run tests: `make test`

## Dependencies

All dependencies are declared in `pyproject.toml` (single source of truth).

- **Runtime**: `pymodbus>=3.6.9,<4.0.0`, Home Assistant core
- **Dev**: `pytest-homeassistant-custom-component`, `ruff`, `pre-commit`, `pytest`, `pytest-asyncio`

## Branch Strategy

- **`main`**: single branch -- all development and releases happen here
- **Feature branches**: created from `main`, named `feat/...`, `fix/...`, or `chore/...`
- **PRs to `main`**: squash-merged (one commit per PR)
- **Release flow**: `make bump` on `main` -> commit -> push -> create GitHub release with tag

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow.

## Git Conventions

- **No AI signature**: Do not add "Co-Authored-By: Claude..." in commit messages
- Follow conventional commit format when appropriate
- **Changelog**: every PR must update `CHANGELOG.md` under `[Unreleased]` (Keep a Changelog format)

## Documentation

Detailed documentation is in [`docs/`](docs/):
- [Architecture](docs/architecture.md) -- hexagonal layers, data flow, domain matrix
- [Development guides](docs/development/) -- getting started, adding entities, registers, profiles
- [Reference](docs/reference/) -- entity reference, entity patterns, domain services, quality scale
- [Gateway docs](docs/gateway/) -- register maps, scan reference, datasheets

## Version Management

Version is defined in two files (kept in sync by `make bump`):
- `manifest.json`: `"version"` -- **source of truth** (read by HA core + HACS at runtime)
- `pyproject.toml`: `version` -- metadata only (uv/build tools)

Use `make bump` to increment the last numeric segment and update both files automatically.
