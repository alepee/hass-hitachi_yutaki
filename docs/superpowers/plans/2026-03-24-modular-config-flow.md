# Modular Gateway Config Flow — Implementation Plan (revised)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace gateway-specific logic in config_flow.py with a protocol-based system where each gateway declares its own configuration steps.

**Architecture:** Each gateway implements `GatewayConfigProvider` (a Python Protocol) that declares step IDs, schemas, and processing logic. Both the config flow and options flow consume the same provider, iterating over `provider.config_steps()`. Dynamic `setattr` registration on the flow instance bridges HA's introspection-based step routing (`async_step_<step_id>`) to a single generic `_handle_provider_step` handler.

**Tech Stack:** Python 3.12, voluptuous, Home Assistant ConfigFlow, Protocol (typing)

**Spec:** `docs/superpowers/specs/2026-03-20-modular-config-flow-design.md`

**Base branch:** `main` (v2.1.0-beta.1, pre-2016 support already merged)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `api/config_providers/__init__.py` | Protocol + dataclasses + registry |
| Create | `api/config_providers/atw_mbs_02.py` | ATW-MBS-02 provider (connection + variant) |
| Create | `api/config_providers/hc_a_mb.py` | HC-A-MB provider (connection only) |
| Modify | `config_flow.py` | Replace gateway-specific steps with generic orchestrator |
| Modify | `translations/en.json` | Provider-prefixed step IDs |
| Modify | `translations/fr.json` | Same |
| Modify | `translations/nl.json` | Same |
| Modify | `translations/ro.json` | Same |
| Create | `tests/api/config_providers/__init__.py` | Package init |
| Create | `tests/api/config_providers/test_atw_mbs_02.py` | Provider unit tests |
| Create | `tests/api/config_providers/test_hc_a_mb.py` | Provider unit tests |
| Modify | `tests/test_config_flow.py` | Update for new step routing |

All paths relative to `custom_components/hitachi_yutaki/` unless prefixed with `tests/`.

## Key Design Decisions

1. **Step IDs are owned by the provider** — `atw_mbs_02_connection`, `atw_mbs_02_variant`, `hc_a_mb_connection`. No generic `gateway_config` or `connection` step IDs.

2. **Both config flow and options flow use the same provider** — they iterate over the same `config_steps()` list and use the same `step_schema()`/`process_step()` methods.

3. **Dynamic `setattr` for HA routing** — HA finds step handlers via `async_step_<step_id>()`. Since provider step IDs are dynamic, we register them at runtime pointing to a single `_handle_provider_step()`. Well-documented with docstrings.

4. **`POWER_SCHEMA` stays global** — the power/sensors step is post-provider, not gateway-specific. It stays in config_flow.py.

5. **`async_validate_connection` stays in config_flow.py** — final validation (system_state check, unique_id, create_entry) is common to all gateways.

6. **Repair flow stays unchanged** — intentionally simplified, outside provider scope.

7. **No config entry schema changes** — `gateway_type`, `gateway_variant`, connection params remain identical.

8. **Translation keys** — old generic keys (`gateway_config`, `connection`, `gateway_variant`) are replaced by provider-prefixed keys in both `config.step.*` and `options.step.*`.

---

### Task 1: Create the Protocol, dataclasses, and registry

**Files:**
- Create: `custom_components/hitachi_yutaki/api/config_providers/__init__.py`

- [ ] **Step 1: Create the config_providers package**

Create the `__init__.py` with:
- Module docstring explaining the provider pattern, step ID conventions, translation requirements, and how `setattr` routing works
- `StepSchema` dataclass: `schema: vol.Schema`, `description_placeholders: dict[str, str]`
- `StepOutcome` dataclass: `errors: dict[str, str] | None`, `config_data: dict[str, Any] | None`, `detected_profiles: list[str] | None`
- `GatewayConfigProvider` Protocol with:
  - `config_steps() → list[str]`
  - `step_schema(step_id: str, context: dict[str, Any]) → StepSchema`
  - `async process_step(hass: HomeAssistant, step_id: str, user_input: dict[str, Any], context: dict[str, Any]) → StepOutcome`
- `GATEWAY_CONFIG_PROVIDERS` registry dict (initially empty — populated by Task 2 and 3)

Note: imports of concrete providers at the bottom of the file (after class definitions) to avoid circular imports. These will be added in Tasks 2-3.

- [ ] **Step 2: Verify module imports**

```bash
uv run python -c "from custom_components.hitachi_yutaki.api.config_providers import GatewayConfigProvider, StepSchema, StepOutcome; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/hitachi_yutaki/api/config_providers/
git commit -m "feat: add GatewayConfigProvider protocol and dataclasses

Protocol-based system where each gateway declares its own config flow
steps. Includes StepSchema, StepOutcome, and provider registry.

See docs/superpowers/specs/2026-03-20-modular-config-flow-design.md"
```

---

### Task 2: Create ATW-MBS-02 config provider

**Files:**
- Create: `custom_components/hitachi_yutaki/api/config_providers/atw_mbs_02.py`

This provider extracts all ATW-MBS-02-specific logic from config_flow.py.

- [ ] **Step 1: Create the provider**

Read `config_flow.py` to understand the current logic for:
- Connection schema (lines 60-73: `GATEWAY_SCHEMA`)
- Connection testing (lines 263-299: `_test_connection()`)
- Variant auto-detection (lines 301-352: `_detect_variant()`)
- Profile detection (lines 354-401: `_detect_and_store_profiles()`)

The `AtwMbs02ConfigProvider` class must:

1. `config_steps()` → `["atw_mbs_02_connection", "atw_mbs_02_variant"]`

2. `step_schema("atw_mbs_02_connection", context)` → schema with:
   - `name` (optional, default "Hitachi Heat Pump")
   - `modbus_host` (required, default "192.168.0.4")
   - `modbus_port` (required, default 502)
   - `modbus_device_id` (required, default 1, range 1-247)
   - `scan_interval` (optional, default 5)

3. `process_step("atw_mbs_02_connection", user_input, context)` →
   - Store connection params in config_data
   - Test Modbus TCP connectivity (reuse logic from `_test_connection()`)
   - On success: return StepOutcome(config_data={connection params})
   - On failure: return StepOutcome(errors={"base": "cannot_connect"})

4. `step_schema("atw_mbs_02_variant", context)` →
   - Run auto-detection using connection params from context (reuse logic from `_detect_variant()`)
   - Return schema with gen1/gen2 selector, default from auto-detection
   - Include `description_placeholders` with `model_decoder_url` and `detected_variant`

5. `process_step("atw_mbs_02_variant", user_input, context)` →
   - Store chosen variant in config_data
   - Create register map for chosen variant
   - Run profile detection (reuse logic from `_detect_and_store_profiles()`)
   - Return StepOutcome(config_data={"gateway_variant": variant}, detected_profiles=[...])

Key imports from current codebase:
- `GATEWAY_INFO`, `create_register_map` from `..`
- `GATEWAY_VARIANTS` from `..modbus.registers`
- `PROFILES` from `...profiles`
- Constants from `...const` (CONF_MODBUS_HOST, DEFAULT_HOST, etc.)
- pymodbus exceptions

- [ ] **Step 2: Add to registry**

In `api/config_providers/__init__.py`, add import and registry entry:
```python
from .atw_mbs_02 import AtwMbs02ConfigProvider
GATEWAY_CONFIG_PROVIDERS["modbus_atw_mbs_02"] = AtwMbs02ConfigProvider
```

- [ ] **Step 3: Verify**

```bash
uv run python -c "from custom_components.hitachi_yutaki.api.config_providers import GATEWAY_CONFIG_PROVIDERS; print(GATEWAY_CONFIG_PROVIDERS)"
```

- [ ] **Step 4: Commit**

```bash
git add custom_components/hitachi_yutaki/api/config_providers/
git commit -m "feat: add ATW-MBS-02 config provider

Extracts connection testing, variant auto-detection, and profile
detection from config_flow.py into a GatewayConfigProvider.
Steps: atw_mbs_02_connection, atw_mbs_02_variant"
```

---

### Task 3: Create HC-A-MB config provider

**Files:**
- Create: `custom_components/hitachi_yutaki/api/config_providers/hc_a_mb.py`

Single step provider — connection with unit_id + profile detection.

- [ ] **Step 1: Create the provider**

`HcAMbConfigProvider` class:

1. `config_steps()` → `["hc_a_mb_connection"]`

2. `step_schema("hc_a_mb_connection", context)` → schema with:
   - Same fields as ATW-MBS-02 connection (name, host, port, device_id, scan_interval)
   - **Plus** `unit_id` (required, default 0, range 0-15) — HC-A-MB specific

3. `process_step("hc_a_mb_connection", user_input, context)` →
   - Store connection params including unit_id in config_data
   - Test connectivity
   - Create HC-A-MB register map (uses unit_id for addressing)
   - Run profile detection
   - Return StepOutcome(config_data={all params}, detected_profiles=[...])

- [ ] **Step 2: Add to registry**

```python
from .hc_a_mb import HcAMbConfigProvider
GATEWAY_CONFIG_PROVIDERS["modbus_hc_a_mb"] = HcAMbConfigProvider
```

- [ ] **Step 3: Verify and commit**

```bash
git add custom_components/hitachi_yutaki/api/config_providers/
git commit -m "feat: add HC-A-MB config provider

Single step provider with unit_id support. Handles connection
testing and profile detection.
Steps: hc_a_mb_connection"
```

---

### Task 4: Refactor config flow to use orchestrator

**Files:**
- Modify: `custom_components/hitachi_yutaki/config_flow.py`

This is the core refactoring — config_flow.py becomes a thin orchestrator.

- [ ] **Step 1: Update imports**

Replace:
```python
from .api import GATEWAY_INFO, create_register_map
from .api.modbus.registers import GATEWAY_VARIANTS
```

With:
```python
from .api import GATEWAY_INFO, create_register_map
from .api.config_providers import GATEWAY_CONFIG_PROVIDERS
```

Remove `GATEWAY_VARIANTS` import.
Keep `create_register_map` (still needed by `async_validate_connection`).
Remove constants only used by deleted gateway-specific code (`DEFAULT_UNIT_ID`, `CONF_UNIT_ID` if no longer needed in this file).

- [ ] **Step 2: Remove `GATEWAY_SCHEMA`**

Delete the module-level `GATEWAY_SCHEMA` constant — providers own their schemas now.

- [ ] **Step 3: Refactor `HitachiYutakiConfigFlow.__init__`**

Replace:
```python
self.gateway_type: str | None = None
self.gateway_variant: str | None = None
self.basic_config: dict[str, Any] = {}
self.all_data: dict[str, Any] = {}
self.detected_profiles: list[str] = []
```

With:
```python
self.gateway_type: str | None = None
self._provider: Any = None  # GatewayConfigProvider instance
self._provider_steps: list[str] = []
self._current_step_index: int = 0
self._step_context: dict[str, Any] = {}
self.detected_profiles: list[str] = []
```

- [ ] **Step 4: Refactor `async_step_user`**

```python
async def async_step_user(self, user_input=None):
    """Handle the initial step (gateway selection)."""
    if user_input is not None:
        self.gateway_type = user_input["gateway_type"]

        # Instantiate the config provider for this gateway
        provider_class = GATEWAY_CONFIG_PROVIDERS[self.gateway_type]
        self._provider = provider_class()
        self._provider_steps = self._provider.config_steps()
        self._current_step_index = 0

        # Register dynamic step methods for HA routing.
        # HA dispatches form submissions by calling async_step_<step_id>()
        # via introspection. Since provider step IDs are dynamic (declared
        # at runtime by each gateway), we register them here so HA can
        # find them. All provider steps route to _handle_provider_step.
        for step_id in self._provider_steps:
            setattr(self, f"async_step_{step_id}", self._handle_provider_step)

        # Show first provider step
        return await self._handle_provider_step()

    return self.async_show_form(
        step_id="user", data_schema=GATEWAY_SELECTION_SCHEMA
    )
```

- [ ] **Step 5: Add `_handle_provider_step`**

```python
async def _handle_provider_step(self, user_input=None):
    """Generic handler for all gateway provider configuration steps.

    This method handles every step declared by the gateway's
    GatewayConfigProvider. HA routes to it via dynamically registered
    async_step_<step_id> methods (see async_step_user).

    Flow:
    1. First call (user_input=None): get schema from provider, show form
    2. Submission (user_input=dict): pass to provider's process_step()
       - If errors: re-show form with errors
       - If ok: merge config_data into context, advance to next step
       - If last step and detected_profiles set: go to profile selection
    """
    step_id = self._provider_steps[self._current_step_index]

    if user_input is not None:
        outcome = await self._provider.process_step(
            self.hass, step_id, user_input, self._step_context
        )

        if outcome.errors:
            step_schema = self._provider.step_schema(step_id, self._step_context)
            return self.async_show_form(
                step_id=step_id,
                data_schema=step_schema.schema,
                description_placeholders=step_schema.description_placeholders,
                errors=outcome.errors,
            )

        if outcome.config_data:
            self._step_context.update(outcome.config_data)

        if outcome.detected_profiles is not None:
            self.detected_profiles = outcome.detected_profiles

        self._current_step_index += 1
        if self._current_step_index >= len(self._provider_steps):
            return await self.async_step_profile()

        step_id = self._provider_steps[self._current_step_index]

    step_schema = self._provider.step_schema(step_id, self._step_context)
    return self.async_show_form(
        step_id=step_id,
        data_schema=step_schema.schema,
        description_placeholders=step_schema.description_placeholders,
    )
```

- [ ] **Step 6: Delete old gateway-specific methods and helpers**

Delete from `HitachiYutakiConfigFlow`:
- `async_step_gateway_config()`
- `async_step_gateway_variant()`
- `_test_connection()`
- `_detect_variant()`
- `_detect_and_store_profiles()`

- [ ] **Step 7: Update `async_step_power`**

Use `self._step_context` instead of `self.basic_config`:

```python
async def async_step_power(self, user_input=None):
    if user_input is not None:
        config = {
            "gateway_type": self.gateway_type,
            **self._step_context,
            **user_input,
        }
        return await self.async_validate_connection(config)
    ...
```

- [ ] **Step 8: Update `async_step_profile`**

Use `self._step_context` instead of `self.basic_config`:

```python
if user_input is not None:
    self._step_context["profile"] = user_input["profile"]
    return await self.async_step_power()
```

- [ ] **Step 9: Refactor `HitachiYutakiOptionsFlow`**

Apply the same provider pattern:

In `__init__`:
```python
self._collected: dict[str, Any] = {}
self._provider: Any = None
self._provider_steps: list[str] = []
self._current_step_index: int = 0
self._step_context: dict[str, Any] = {}
```

In `async_step_init`: after gateway selection, instantiate provider, register step methods via `setattr`, pre-populate `self._step_context` with current `config_entry.data`, then go to first provider step.

Add `_handle_provider_step` (same pattern as config flow). After provider steps: go to `async_step_profile`.

Delete:
- `async_step_connection()`
- `async_step_gateway_variant()`

Keep unchanged:
- `async_step_profile()`
- `async_step_sensors()`

- [ ] **Step 10: Run `make check`**

- [ ] **Step 11: Commit**

```bash
git add custom_components/hitachi_yutaki/config_flow.py
git commit -m "refactor: replace gateway-specific config flow with provider orchestrator

Config flow and options flow now delegate to GatewayConfigProvider
instances. Dynamic setattr registration bridges HA step routing
to a single generic handler. No gateway-specific logic remains."
```

---

### Task 5: Update translations

**Files:**
- Modify: all 4 files in `custom_components/hitachi_yutaki/translations/`

- [ ] **Step 1: Update en.json**

In `config.step` section:
- Remove `gateway_config` entry
- Remove `gateway_variant` entry
- Add `atw_mbs_02_connection` with title/description/data fields from old `gateway_config` (WITHOUT unit_id)
- Add `atw_mbs_02_variant` with title/description/data from old `gateway_variant` (keep `{detected_variant}` and `{model_decoder_url}` placeholders)
- Add `hc_a_mb_connection` with same connection fields as ATW PLUS unit_id field label

In `options.step` section:
- Remove `connection` entry
- Remove `gateway_variant` entry
- Add `atw_mbs_02_connection` (same content as config.step)
- Add `atw_mbs_02_variant` (same content as config.step)
- Add `hc_a_mb_connection` (same content as config.step)

Keep unchanged: `user`, `init`, `profile`, `power`, `sensors`, `repair`, `telemetry`

Remove `gateway_variant` from `selector` section (provider manages this via its own schema with `translation_key`).

- [ ] **Step 2: Update fr.json, nl.json, ro.json**

Same structural changes, translated content.

- [ ] **Step 3: Run `make check`**

Verify hassfest doesn't complain about URLs in descriptions (should use `{model_decoder_url}` placeholder).

- [ ] **Step 4: Commit**

```bash
git add custom_components/hitachi_yutaki/translations/
git commit -m "feat: rename translation keys for provider-based config flow

Step IDs now use gateway-prefixed names matching the providers:
atw_mbs_02_connection, atw_mbs_02_variant, hc_a_mb_connection.
Shared between config and options flows."
```

---

### Task 6: Update and add tests

**Files:**
- Create: `tests/api/config_providers/__init__.py`
- Create: `tests/api/config_providers/test_atw_mbs_02.py`
- Create: `tests/api/config_providers/test_hc_a_mb.py`
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Create ATW-MBS-02 provider tests**

Read existing test patterns in `tests/test_config_flow.py` (mock helpers, patching patterns).

Test class `TestAtwMbs02ConfigProvider`:
- `test_config_steps` — returns 2 steps in correct order
- `test_connection_schema_fields` — schema has host/port/device_id/scan_interval/name, NO unit_id
- `test_variant_schema_fields` — schema has gateway_variant selector
- `test_variant_schema_includes_auto_detection_placeholder` — description_placeholders has `detected_variant` and `model_decoder_url`
- `test_process_connection_success` — mock API client, verify config_data returned with connection params
- `test_process_connection_failure` — verify errors={"base": "cannot_connect"}
- `test_process_variant_detects_profiles` — mock API client with profile data, verify detected_profiles in outcome
- `test_process_variant_stores_gateway_variant` — verify config_data includes gateway_variant

- [ ] **Step 2: Create HC-A-MB provider tests**

Test class `TestHcAMbConfigProvider`:
- `test_config_steps` — returns 1 step
- `test_connection_schema_has_unit_id` — schema includes unit_id field (range 0-15)
- `test_process_connection_success_with_profiles` — verify both config_data and detected_profiles returned
- `test_process_connection_failure` — verify errors

- [ ] **Step 3: Update config flow tests**

Read current `tests/test_config_flow.py`. Key changes:

Update helper functions:
- `_advance_to_gateway_config()` → `_advance_to_provider_step(hass, flow_id, gateway_type)` — advances to first provider step, returns result with correct step_id
- `_advance_to_gateway_variant()` → `_advance_through_connection(hass, flow_id)` — fills connection form, returns result at variant step

Update all step_id assertions:
- `"gateway_config"` → `"atw_mbs_02_connection"` (for ATW tests)
- `"gateway_variant"` → `"atw_mbs_02_variant"` (for ATW tests)
- `"connection"` (options) → `"atw_mbs_02_connection"` (for ATW options tests)

Update patches:
- Add `GATEWAY_CONFIG_PROVIDERS` patches where needed
- Keep `GATEWAY_INFO` and `create_register_map` patches (still used by providers and `async_validate_connection`)

Add new tests:
- `test_setattr_registers_provider_steps` — verify dynamic step methods exist after gateway selection
- `test_hc_a_mb_skips_variant_step` — verify HC-A-MB goes directly from connection to profile
- `test_orchestrator_handles_provider_errors` — verify errors from provider re-display the form
- `test_options_flow_uses_same_provider_steps` — verify options flow iterates same provider steps as config flow

- [ ] **Step 4: Run full test suite**

```bash
make test
```

Fix any failures. Expect ~15-20 tests to need step_id assertion updates.

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test: add provider unit tests and update config flow tests

Unit tests for ATW-MBS-02 and HC-A-MB providers covering schemas,
step processing, and profile detection. Config flow tests updated
for provider-based step routing with gateway-prefixed step IDs."
```

---

### Task 7: Final verification

- [ ] **Step 1: Full test suite**

```bash
make test
```

- [ ] **Step 2: Lint and format**

```bash
make check
```

- [ ] **Step 3: Verify no gateway-specific conditionals remain**

```bash
grep -n "gateway_type.*==" custom_components/hitachi_yutaki/config_flow.py
```

Expected: only in `async_step_power` (assembling config dict) and `async_validate_connection` (creating register map). No `if gateway_type == "modbus_hc_a_mb"` style branches.

- [ ] **Step 4: Commit and push**

```bash
git push -u origin refactor/modular-config-flow
```

---

## Verification Checklist

- [ ] `GatewayConfigProvider` protocol with `StepSchema` and `StepOutcome` dataclasses
- [ ] `AtwMbs02ConfigProvider` with `atw_mbs_02_connection` + `atw_mbs_02_variant` steps
- [ ] `HcAMbConfigProvider` with `hc_a_mb_connection` step (includes unit_id)
- [ ] Config flow orchestrator uses `setattr` + `_handle_provider_step`
- [ ] Options flow uses same provider pattern
- [ ] No gateway-specific `if` conditionals remain in config_flow.py (except final validation)
- [ ] Translations use gateway-prefixed step IDs, shared between config and options flows
- [ ] Hassfest passes (no raw URLs in translations)
- [ ] Provider unit tests pass
- [ ] Config flow integration tests pass
- [ ] `make test` — all tests pass
- [ ] `make check` — lint clean
- [ ] Repair flow continues to work independently (not modified)
