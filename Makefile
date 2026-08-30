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
bump: ## Bump version — usage: make bump [PART=patch|minor|major|beta] (default: patch)
	@python3 scripts/bump_version.py $(PART)

.PHONY: version
version: ## Show current version
	@echo $(VERSION)

# —— Telemetry backend ——————————————————————————————————

WORKER_DIR := backend/worker

# Load the Worker's local .env (gitignored) so make sees the same account
# wrangler would read from it. A missing file is fine: the guard below is what
# reports it, with an actionable message.
-include $(WORKER_DIR)/.env
export CLOUDFLARE_ACCOUNT_ID

# Refuse to act without an explicit account. wrangler otherwise falls back to
# whichever account the local OAuth token happens to belong to, which silently
# deploys the Worker somewhere else and auto-provisions an empty R2 bucket
# there instead of failing.
define require_cf_account
	@test -n "$(CLOUDFLARE_ACCOUNT_ID)" || { \
		echo "CLOUDFLARE_ACCOUNT_ID is not set."; \
		echo "Put 'CLOUDFLARE_ACCOUNT_ID=<id>' in $(WORKER_DIR)/.env (gitignored),"; \
		echo "or export it. Find the id at dash.cloudflare.com/<account_id>."; \
		exit 1; \
	}
endef

.PHONY: worker-install
worker-install: ## Install the telemetry Worker's dependencies
	cd $(WORKER_DIR) && npm ci

.PHONY: worker-test
worker-test: ## Run the telemetry Worker test suite
	cd $(WORKER_DIR) && npm test

.PHONY: worker-deploy
worker-deploy: ## Deploy the telemetry Worker (requires CLOUDFLARE_ACCOUNT_ID)
	$(require_cf_account)
	cd $(WORKER_DIR) && npm test && npx wrangler deploy

.PHONY: worker-deploy-dry
worker-deploy-dry: ## Build the Worker without deploying (requires CLOUDFLARE_ACCOUNT_ID)
	$(require_cf_account)
	cd $(WORKER_DIR) && npx wrangler deploy --dry-run

# —— Diagnostics ———————————————————————————————————————

.PHONY: scan
scan: ## Scan Modbus gateway registers (use SCAN_ARGS for options, redirect stdout for file output)
	uv run python scripts/scan_gateway.py $(SCAN_ARGS)

# —— Help ——————————————————————————————————————————————

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
