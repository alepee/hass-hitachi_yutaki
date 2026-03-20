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

- `config_steps() → list[str]` — ordered list of step IDs, prefixed by gateway identifier
- `step_schema(step_id, context) → StepSchema` — form schema for a step
- `async process_step(hass, step_id, user_input, context) → StepOutcome` — process input, return result

The `context` is a `dict[str, Any]` accumulating `config_data` from all previous steps. Each step can read data set by earlier steps (e.g., the variant step reads host/port set by the connection step).

### Step ID Convention

Step IDs are chosen by each gateway and prefixed by the gateway identifier to avoid collisions and ensure explicit translations:

- ATW-MBS-02: `atw_mbs_02_connection`, `atw_mbs_02_variant`
- HC-A-MB: `hc_a_mb_connection`

These IDs are arbitrary and gateway-owned. The config flow orchestrator treats them as opaque strings.

### HA Step Routing Mechanism

Home Assistant's `ConfigFlow` routes user input by calling `async_step_<step_id>()` via introspection. Since provider step IDs are dynamic (declared at runtime), there is no static `async_step_atw_mbs_02_connection()` method in the class.

**Solution:** When the provider is instantiated (after gateway selection in `async_step_user`), the orchestrator dynamically registers step methods on the flow instance using `setattr`:

```python
for step_id in self._provider.config_steps():
    setattr(self, f"async_step_{step_id}", self._handle_provider_step)
```

All provider steps route to the same `_handle_provider_step` method, which uses `self._current_step_index` to know which step is being processed.

This approach:
- Preserves standard HA step routing (no framework hacks)
- Allows each step to have its own translation key (`config.step.<step_id>`)
- Keeps the orchestrator generic — it never knows the step names in advance

**Documentation requirement:** This mechanism must be clearly documented with a docstring on the orchestrator explaining:
1. Why `setattr` is used (HA routing constraint)
2. How step IDs map to translations
3. How to add a new gateway (implement `GatewayConfigProvider`, add translations, register in `GATEWAY_CONFIG_PROVIDERS`)

### Translation Convention

Translations for provider steps must live under the standard HA paths:
- `config.step.<step_id>.title` — step title
- `config.step.<step_id>.description` — step description
- `config.step.<step_id>.data.<field>` — field labels
- `options.step.<step_id>.title` (etc.) — same for options flow

Both config and options flows use the **same step IDs** from the provider, so translations are shared.

Each provider is responsible for documenting which step IDs and translation keys it requires.

### Provider Implementations

```
api/config_providers/
├── __init__.py          ← Protocol + StepSchema + StepOutcome + GATEWAY_CONFIG_PROVIDERS
├── atw_mbs_02.py        ← AtwMbs02ConfigProvider
└── hc_a_mb.py           ← HcAMbConfigProvider
```

**AtwMbs02ConfigProvider** — steps: `atw_mbs_02_connection`, `atw_mbs_02_variant`

- `atw_mbs_02_connection`: schema with host/port/device_id/scan_interval. `process_step` tests Modbus TCP connectivity.
- `atw_mbs_02_variant`: schema with gen1/gen2 selector, pre-filled via auto-detection. `process_step` creates the register map for the chosen variant and detects profiles. Returns `detected_profiles` in the outcome.

**HcAMbConfigProvider** — steps: `hc_a_mb_connection`

- `hc_a_mb_connection`: schema with host/port/device_id/scan_interval/unit_id. `process_step` tests connectivity, creates register map, and detects profiles in one step. Returns `detected_profiles` in the outcome.

### Provider Registry

In `api/config_providers/__init__.py`:

```python
GATEWAY_CONFIG_PROVIDERS: dict[str, type[GatewayConfigProvider]] = {
    "modbus_atw_mbs_02": AtwMbs02ConfigProvider,
    "modbus_hc_a_mb": HcAMbConfigProvider,
}
```

### Config Flow Orchestrator

`config_flow.py` becomes a thin orchestrator with no gateway-specific logic:

1. `async_step_user` — gateway selection → instantiates the provider → registers dynamic step methods via `setattr` → advances to first provider step
2. `_handle_provider_step` — generic handler for all provider steps:
   - On first call (no `user_input`): gets schema from provider (`step_schema()`), shows form with `step_id` from provider
   - On submission: passes input to provider (`process_step()`)
   - If errors → re-shows form
   - If ok → merges `config_data` into context, advances to next step
   - If last step → stores `detected_profiles`, moves to `async_step_profile`
3. `async_step_profile` / `async_step_power` / `async_validate_connection` — unchanged

State maintained in the flow instance:
- `self._provider: GatewayConfigProvider` — the current provider
- `self._provider_steps: list[str]` — ordered step IDs
- `self._current_step_index: int` — position in the step list
- `self._step_context: dict[str, Any]` — accumulated config data

### Options Flow

Same pattern as config flow. The options flow orchestrator:
1. `async_step_init` — gateway selection → instantiates provider → registers step methods → first step
2. `_handle_provider_step` — same generic handler
3. After provider steps → `async_step_profile` → `async_step_sensors`

Both flows use the same provider instances and the same step IDs, so translations are shared.

### Repair Flow

The repair flow (`repairs.py`) stays unchanged. It is intentionally simplified (gateway_type + profile selection only) and does not need the provider infrastructure. It handles broken config entries where the full setup flow would be overkill.

### What Moves Out of config_flow.py

- `async_step_gateway_config` → replaced by `_handle_provider_step`
- `async_step_gateway_variant` → replaced by `_handle_provider_step`
- `_test_connection()` → moves into providers
- `_detect_variant()` → moves into ATW-MBS-02 provider
- `_detect_and_store_profiles()` → moves into providers (each does it in its last step)
- `GATEWAY_SCHEMA` → each provider declares its own schema
- All `if gateway_type == ...` conditionals

### What Stays in config_flow.py

- `async_step_user` (gateway selection + provider instantiation)
- `_handle_provider_step` (generic orchestrator)
- `async_step_profile` / `async_step_power` / `async_validate_connection`
- Config entry migration logic (v2.4)

### No Config Entry Changes

The stored data remains identical: `gateway_type`, `gateway_variant`, `modbus_host`, etc. Only the code path to collect it changes.

### Architecture Boundaries

Two distinct responsibilities, not merged:

- **Configuration** (how to set up the connection) → `GatewayConfigProvider`
- **Communication** (how to talk to the heat pump) → `ApiClient` + `RegisterMap`

The `ConfigProvider` produces the data needed to instantiate the right `ApiClient` with the right `RegisterMap`. It does not encapsulate them. This follows the hexagonal architecture: the config flow (HA adapter) consumes a protocol (port), and each gateway provides its implementation.

### Testing

- **Unit tests per provider** — pure Python, mock `hass`. Test `config_steps()`, `step_schema()`, `process_step()` in isolation. Verify schemas, error handling, profile detection.
- **Orchestrator tests** — mock the provider, verify step iteration, `setattr` registration, error re-display, transition to profile step.
- **Integration tests** — end-to-end config flow with real providers (existing test pattern).

### Adding a New Gateway (contributor guide)

1. Create `api/config_providers/my_gateway.py` implementing `GatewayConfigProvider`
2. Choose gateway-prefixed step IDs (e.g., `my_gateway_connection`)
3. Add translations under `config.step.<step_id>` and `options.step.<step_id>` in all language files
4. Register in `GATEWAY_CONFIG_PROVIDERS`
5. Add `GatewayInfo` entry in `api/__init__.py`
6. Write unit tests for the provider
