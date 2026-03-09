# Getting Started

This is the primary onboarding guide for contributors to the Hitachi Yutaki Home Assistant integration. It covers environment setup, running the project locally, and the workflow for submitting changes.

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** -- Python package manager (used via Makefile)
- **git**

## Setup

1. **Fork and clone** the repository:

```bash
git clone https://github.com/<your-username>/hass-hitachi_yutaki.git
cd hass-hitachi_yutaki
```

2. **Run the full project setup** (installs dependencies and pre-commit hooks):

```bash
make setup
```

3. **Verify** everything works:

```bash
make check && make test
```

If both commands pass, your environment is ready.

## Running Home Assistant Locally

Start a development instance of Home Assistant with the integration loaded:

```bash
make ha-run
```

Home Assistant will be available at `http://localhost:8123`.

To use a custom port, add the following to `config/configuration.yaml`:

```yaml
http:
  server_port: 9125
```

### Dev Container Alternative

This repository includes a Dev Container configuration for a fully pre-configured environment:

1. Install [Visual Studio Code](https://code.visualstudio.com/) and the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers).
2. Open the repository in VS Code.
3. When prompted to "Reopen in Container", click "Yes" (or press F1 and select "Dev Containers: Rebuild and Reopen in Container").

The container ships with all dependencies, pre-commit hooks, and a ready-to-use HA development instance.

## Project Structure

```
hass-hitachi_yutaki/
├── custom_components/hitachi_yutaki/
│   ├── domain/            # Pure business logic (no HA dependencies)
│   ├── adapters/          # Bridges domain with Home Assistant
│   ├── entities/          # Domain-driven entity organization
│   ├── api/               # Modbus communication layer
│   ├── profiles/          # Heat pump model profiles
│   └── translations/      # Language files
├── tests/                 # Test suite (pytest)
│   ├── domain/            # Domain layer tests (pure Python)
│   └── profiles/          # Profile detection tests
├── docs/                  # Developer documentation
└── documentation/         # Architecture and investigation docs
```

The codebase follows a hexagonal (ports and adapters) architecture. See [Architecture](../architecture.md) for a detailed breakdown of each layer and the design principles behind them.

## Make Targets

Run `make help` to list all available targets. Here is the full reference:

| Target | Description |
|--------|-------------|
| `make install` | Install all dependencies (dev included) |
| `make setup` | Full project setup (deps + pre-commit hooks) |
| `make upgrade-deps` | Upgrade all deps (HA version follows `pytest-homeassistant-custom-component`) |
| `make lint` | Run ruff linter with auto-fix |
| `make format` | Run ruff formatter |
| `make check` | Run all code quality checks (lint + format) |
| `make test` | Run all tests |
| `make test-domain` | Run domain layer tests only (pure Python, no HA) |
| `make test-coverage` | Run tests with coverage report |
| `make ha-run` | Start a local HA dev instance with debug config |
| `make ha-upgrade` | Temporary HA upgrade (reset by `make install`) |
| `make ha-dev-branch` | Temporary HA dev branch (reset by `make install`) |
| `make ha-version` | Temporary HA specific version (reset by `make install`) |
| `make bump` | Bump version (last numeric segment) |
| `make version` | Show current version |

> **Note:** The Home Assistant version in the dev environment is controlled by `pytest-homeassistant-custom-component` via the lockfile. Use `make upgrade-deps` to update it. The `ha-upgrade`, `ha-dev-branch`, and `ha-version` targets are temporary overrides for ad-hoc testing -- `make install` restores the lockfile version.

## Running Tests

```bash
# Run the full test suite
make test

# Run domain layer tests only (pure Python, fast, no HA mocks)
make test-domain

# Run tests with coverage report
make test-coverage
```

Domain tests (`tests/domain/`) exercise the business logic in isolation and run significantly faster than integration-level tests because they do not require Home Assistant.

## Code Quality

Code style is enforced by **Ruff** (linting and formatting) with a Home Assistant-specific ruleset defined in `.ruff.toml`. Pre-commit hooks run Ruff automatically on every commit.

Before pushing, always run:

```bash
make check
```

This runs both the linter (with auto-fix) and the formatter in a single command.

## Your First Contribution

1. **Create a branch** from `main`:

```bash
git checkout main && git pull
git checkout -b feat/my-feature
```

2. **Make your changes**, following the hexagonal architecture conventions.

3. **Update the changelog** -- add an entry under `[Unreleased]` in `CHANGELOG.md` using [Keep a Changelog](https://keepachangelog.com/) format.

4. **Run quality checks and tests:**

```bash
make check && make test
```

5. **Commit** using [conventional commit](https://www.conventionalcommits.org/) format:

```bash
git commit -m "feat: add new sensor for X"
```

6. **Open a pull request** targeting the `main` branch. PRs are squash-merged, so each PR becomes a single commit on `main`. All CI checks (tests, lint, HACS/hassfest validation) must pass before merge.

## Further Reading

- [Architecture](../architecture.md) -- hexagonal design, layer responsibilities, and key patterns
- [Adding Entities](adding-entities.md) -- step-by-step guide for creating new entities
- [API Layer & Data Keys](api-data-keys.md) -- API abstraction, data keys, and Modbus implementation
- [Heat Pump Profiles](profiles.md) -- model detection and capability definitions
