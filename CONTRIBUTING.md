# Contributing to Hitachi Yutaki Integration

Thank you for your interest in contributing! This guide explains how to get started and the workflow we follow.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
3. **Install** dependencies:
   ```bash
   uv sync --group dev     # or: make install
   ```
4. **Set up** pre-commit hooks:
   ```bash
   ./scripts/setup
   ```

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Released state. Never push directly. Protected by ruleset. |
| `dev` | Integration branch. Target for all pull requests. |
| Feature branches | Created from `dev`, named `feat/...`, `fix/...`, or `chore/...`. |

### Release Flow

1. `dev` is frozen (no new feature merges)
2. Version is bumped on `dev` (`make bump`)
3. A PR is opened from `dev` to `main`
4. PR is merged (merge commit)
5. A GitHub release is created from `main`

## Making Changes

1. Create a branch from `dev`:
   ```bash
   git checkout dev && git pull
   git checkout -b feat/my-feature
   ```
2. Make your changes, following the [hexagonal architecture](CLAUDE.md#architecture)
3. Run quality checks:
   ```bash
   make check    # lint + format
   make test     # run all tests
   ```
4. Update `CHANGELOG.md` under `[Unreleased]` with your changes (see [Changelog](#changelog))
5. Commit using [conventional commit](https://www.conventionalcommits.org/) format:
   ```bash
   git commit -m "feat: add new sensor for X"
   ```

## Pull Requests

- **Base branch**: always `dev`
- **Squash merged**: each PR becomes a single commit on `dev`
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

- `en.json` is the source of truth — edit it directly when adding new translatable strings
- Other language files can be updated via PR

## Code Style

Code style is enforced automatically:

- **Ruff** handles both linting and formatting (see `.ruff.toml`)
- **Pre-commit hooks** run ruff on every commit
- See [CLAUDE.md](CLAUDE.md#code-quality-standards) for detailed conventions

No manual formatting is needed — just run `make check` before committing.
