.DEFAULT_GOAL := help

MANIFEST := custom_components/hitachi_yutaki/manifest.json
VERSION  := $(shell python3 -c "import json;print(json.load(open('$(MANIFEST)'))['version'])")

# —— Setup ——————————————————————————————————————————————

.PHONY: install
install: ## Install all dependencies (dev included)
	uv sync --group dev

.PHONY: setup
setup: ## Full project setup (deps + pre-commit hooks + system libs)
	./scripts/setup

.PHONY: upgrade-deps
upgrade-deps: ## Upgrade all deps (HA version follows pytest-homeassistant-custom-component)
	uv lock --upgrade
	uv sync --group dev

# —— Quality ————————————————————————————————————————————

.PHONY: lint
lint: ## Run ruff linter with auto-fix
	uv run ruff check custom_components tests --fix

.PHONY: format
format: ## Run ruff formatter
	uv run ruff format custom_components tests

.PHONY: check
check: lint format ## Run all code quality checks (lint + format)

.PHONY: pre-commit
pre-commit: ## Run all pre-commit hooks on the entire codebase
	uv run pre-commit run --all-files

# —— Testing ————————————————————————————————————————————

.PHONY: test
test: ## Run all tests
	uv run pytest

.PHONY: test-domain
test-domain: ## Run domain layer tests only (pure Python, no HA)
	uv run pytest tests/domain/

.PHONY: test-verbose
test-verbose: ## Run all tests with verbose output
	uv run pytest -v

.PHONY: test-coverage
test-coverage: ## Run tests with coverage report
	uv run pytest --cov=custom_components/hitachi_yutaki --cov-report=term-missing

# —— Home Assistant ————————————————————————————————————

.PHONY: ha-run
ha-run: ## Start a local HA dev instance with debug config
	./scripts/develop

.PHONY: ha-upgrade
ha-upgrade: ## Temporary HA upgrade (reset by make install)
	./scripts/upgrade

.PHONY: ha-dev-branch
ha-dev-branch: ## Temporary HA dev branch (reset by make install)
	./scripts/dev-branch

.PHONY: ha-version
ha-version: ## Temporary HA specific version (reset by make install)
	./scripts/specific-version

# —— Release ———————————————————————————————————————————

.PHONY: bump
bump: ## Bump version (last numeric segment)
	@python3 -c " \
	import json, re; \
	mf = '$(MANIFEST)'; \
	m = json.load(open(mf)); \
	old = m['version']; \
	new = re.sub(r'(\d+)$$', lambda x: str(int(x.group())+1), old); \
	m['version'] = new; \
	json.dump(m, open(mf,'w'), indent=2, ensure_ascii=False); \
	open(mf,'a').write('\n'); \
	\
	pt = open('pyproject.toml').read(); \
	pt = pt.replace('version = \"'+old+'\"', 'version = \"'+new+'\"', 1); \
	open('pyproject.toml','w').write(pt); \
	\
	print(f'Bumped {old} → {new}') \
	"

.PHONY: version
version: ## Show current version
	@echo $(VERSION)

# —— Diagnostics ———————————————————————————————————————

.PHONY: scan
scan: ## Scan Modbus gateway registers (use SCAN_ARGS for options, redirect stdout for file output)
	uv run python scripts/scan_gateway.py $(SCAN_ARGS)

# —— Help ——————————————————————————————————————————————

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
