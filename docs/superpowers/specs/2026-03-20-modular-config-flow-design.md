# Modular Gateway Config Flow

**Date:** 2026-03-20
**Branch:** `feat/pre-2016-support`

## Context

The config flow currently has gateway-specific logic hardcoded: conditional schemas (`if hc_a_mb → add unit_id`), variant steps, connection testing, and profile detection all live in `config_flow.py`. As we add more gateways or protocols, this becomes increasingly tangled.

## Design

### Protocol: `GatewayConfigProvider`

Each gateway implements a `GatewayConfigProvider` protocol that declares its own configuration steps. Lives in `api/config_providers/__init__.py`.

**Dataclasses:**

- `StepSchema` — `schema: vol.Schema`, `description_placeholders: dict[str, str]`
- `StepOutcome` — `errors: dict[str, str] | None`, `config_data: dict[str, Any] | None`, `detected_profiles: list[str] | None`

**Protocol methods:**

- `config_steps() → list[str]` — ordered list of step IDs
- `step_schema(step_id, context) → StepSchema` — form schema for a step
- `async process_step(hass, step_id, user_input, context) → StepOutcome` — process input, return result

The `context` is a `dict[str, Any]` accumulating data from previous steps (host, port, variant, etc.).

### Step ID Convention

Step IDs are prefixed by the gateway identifier to avoid collisions and make translations explicit:

- ATW-MBS-02: `atw_mbs_02_connection`, `atw_mbs_02_variant`
- HC-A-MB: `hc_a_mb_connection`

Translations must live under `config.step.<step_id>` and `options.step.<step_id>` in translation files, because the config flow orchestrator calls `async_show_form(step_id=...)` and HA resolves translations by that path.

### Provider Implementations

```
api/config_providers/
├── __init__.py          ← Protocol + StepSchema + StepOutcome
├── atw_mbs_02.py        ← AtwMbs02ConfigProvider
└── hc_a_mb.py           ← HcAMbConfigProvider
```

**AtwMbs02ConfigProvider** — steps: `atw_mbs_02_connection`, `atw_mbs_02_variant`

- `atw_mbs_02_connection`: schema with host/port/device_id/scan_interval. Process tests Modbus TCP connectivity.
- `atw_mbs_02_variant`: schema with gen1/gen2 selector. Process auto-detects variant, then detects profiles using the chosen variant's register map.

**HcAMbConfigProvider** — steps: `hc_a_mb_connection`

- `hc_a_mb_connection`: schema with host/port/device_id/scan_interval/unit_id. Process tests connectivity and detects profiles (no variant step).

### Provider Registry

In `api/config_providers/__init__.py`:

```python
GATEWAY_CONFIG_PROVIDERS = {
    "modbus_atw_mbs_02": AtwMbs02ConfigProvider,
    "modbus_hc_a_mb": HcAMbConfigProvider,
}
```

### Config Flow Orchestrator

`config_flow.py` becomes a thin orchestrator with no gateway-specific logic:

1. `async_step_user` — gateway selection → instantiates the provider → starts first step
2. `async_step_gateway` — generic step that iterates over the provider's steps:
   - Gets schema from provider (`step_schema()`)
   - Shows form (`async_show_form(step_id=<gateway_step_id>)`)
   - Passes input to provider (`process_step()`)
   - If errors → re-shows form
   - If ok → advances to next step, or moves to `async_step_profile` when list is exhausted
3. `async_step_profile` / `async_step_power` / `async_validate_connection` — unchanged

State maintained in the flow: provider instance, current step index, accumulated context.

Options flow follows the same pattern.

### What Moves Out of config_flow.py

- `async_step_gateway_config` → replaced by generic `async_step_gateway`
- `async_step_gateway_variant` → replaced by generic `async_step_gateway`
- `_test_connection()` → moves to ATW-MBS-02 and HC-A-MB providers
- `_detect_variant()` → moves to ATW-MBS-02 provider
- `_detect_and_store_profiles()` → moves to providers (each does it in its last step)
- `GATEWAY_SCHEMA` → each provider declares its own schema
- All `if gateway_type == ...` conditionals

### What Stays in config_flow.py

- `async_step_user` (gateway selection)
- `async_step_gateway` (generic orchestrator)
- `async_step_profile` / `async_step_power` / `async_validate_connection`
- Config entry migration logic

### No Config Entry Changes

The stored data remains identical: `gateway_type`, `gateway_variant`, `modbus_host`, etc. Only the code path to collect it changes.

### Architecture Boundaries

Two distinct responsibilities, not merged:

- **Configuration** (how to set up the connection) → `GatewayConfigProvider`
- **Communication** (how to talk to the heat pump) → `ApiClient` + `RegisterMap`

The `ConfigProvider` produces the data needed to instantiate the right `ApiClient` with the right `RegisterMap`. It does not encapsulate them.

### Testing

- **Unit tests per provider** — pure Python, no HA fixtures. Test `config_steps()`, `step_schema()`, `process_step()` with mocked hass.
- **Orchestrator tests** — mock the provider, verify step iteration, error handling, transition to profile.
- **Integration tests** — end-to-end config flow with real providers (existing test pattern).
