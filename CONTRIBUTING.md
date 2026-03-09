# Contributing to Hitachi Yutaki Integration

Thank you for your interest in contributing!

## Quick Start

1. Fork the repository on GitHub
2. Clone your fork locally
3. Run `make setup` (installs dependencies + pre-commit hooks)
4. Verify: `make check && make test`

For detailed setup instructions, see [Getting Started](docs/development/getting-started.md).

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Single branch for development and releases. Protected by ruleset. |
| Feature branches | Created from `main`, named `feat/...`, `fix/...`, or `chore/...`. |

## Making Changes

1. Create a branch from `main` (`git checkout main && git pull && git checkout -b feat/my-feature`)
2. Follow the [hexagonal architecture](docs/architecture.md)
3. Run `make check && make test`
4. Update `CHANGELOG.md` under `[Unreleased]` (see [Changelog](#changelog))
5. Commit using [conventional commit](https://www.conventionalcommits.org/) format

## Pull Requests

- **Base branch**: always `main`
- **Squash merged**: each PR becomes a single commit on `main`
- Provide a clear description of what changes and why
- All CI checks must pass before merge:
  - **Tests** (HA 2025.1.0 + latest)
  - **Lint** (ruff + translation keys)
  - **Validate** (HACS + hassfest)

## Changelog

Every PR must include an entry under `[Unreleased]` in `CHANGELOG.md`, following the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format:

```markdown
## [Unreleased]

### Added
- New feature description

### Fixed
- Bug fix description
```

Use the appropriate section: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

PRs that don't affect user-facing behavior (CI config, dev tooling) can use the `skip-changelog` label.

## Translations

- `en.json` is the source of truth -- edit it directly when adding new translatable strings
- Other languages can be contributed via [Weblate](https://hosted.weblate.org/engage/hass-hitachi_yutaki/) (no coding required) or via PR
- If editing JSON files directly, check for concurrent Weblate changes on the same keys to avoid merge conflicts

## Code Style

Code style is enforced automatically:

- **Ruff** handles both linting and formatting (see `.ruff.toml`)
- **Pre-commit hooks** run ruff on every commit
- See [CLAUDE.md](CLAUDE.md#code-quality-standards) for detailed conventions

No manual formatting is needed -- just run `make check` before committing.
