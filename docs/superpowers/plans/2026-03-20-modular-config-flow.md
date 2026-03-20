# Modular Gateway Config Flow — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace gateway-specific logic in config_flow.py with a protocol-based system where each gateway declares its own configuration steps.

**Architecture:** Each gateway implements `GatewayConfigProvider` (a Python Protocol) that declares step IDs, schemas, and processing logic. The config flow orchestrator iterates over these steps generically. Dynamic `setattr` registration bridges HA's step routing to the generic handler.

**Tech Stack:** Python 3.12, voluptuous, Home Assistant ConfigFlow, Protocol (typing)

**Spec:** `docs/superpowers/specs/2026-03-20-modular-config-flow-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `api/config_providers/__init__.py` | Protocol + dataclasses + registry |
| Create | `api/config_providers/atw_mbs_02.py` | ATW-MBS-02 provider (connection + variant steps) |
| Create | `api/config_providers/hc_a_mb.py` | HC-A-MB provider (connection step) |
| Modify | `config_flow.py` | Replace gateway-specific steps with generic orchestrator |
| Modify | `translations/en.json` | Rename step keys to gateway-prefixed IDs |
| Modify | `translations/fr.json` | Same |
| Modify | `translations/nl.json` | Same |
| Modify | `translations/ro.json` | Same |
| Create | `tests/api/config_providers/test_atw_mbs_02.py` | Provider unit tests |
| Create | `tests/api/config_providers/test_hc_a_mb.py` | Provider unit tests |
| Modify | `tests/test_config_flow.py` | Update for new step routing |

All paths relative to `custom_components/hitachi_yutaki/` unless prefixed with `tests/`.

---

### Task 1: Create the Protocol and dataclasses

**Files:**
- Create: `custom_components/hitachi_yutaki/api/config_providers/__init__.py`

- [ ] **Step 1: Create the module with Protocol, dataclasses, and registry**

```python
"""Gateway configuration providers.

Each gateway implements GatewayConfigProvider to declare its own
configuration steps. The config flow orchestrator iterates over
these steps generically via dynamic setattr registration.

Step IDs are gateway-prefixed (e.g., 'atw_mbs_02_connection') and
must have matching translation keys under config.step.<step_id>
and options.step.<step_id> in translation files.

See docs/superpowers/specs/2026-03-20-modular-config-flow-design.md
for the full design rationale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import voluptuous as vol

from homeassistant.core import HomeAssistant


@dataclass
class StepSchema:
    """Schema and metadata for a config flow step."""

    schema: vol.Schema
    description_placeholders: dict[str, str] = field(default_factory=dict)


@dataclass
class StepOutcome:
    """Result of processing a config flow step.

    - errors: validation errors to re-display the form (keys match schema fields or "base")
    - config_data: data to accumulate into the flow context for subsequent steps
    - detected_profiles: list of detected heat pump profile keys (set by the last step)
    """

    errors: dict[str, str] | None = None
    config_data: dict[str, Any] | None = None
    detected_profiles: list[str] | None = None


class GatewayConfigProvider(Protocol):
    """Protocol for gateway-specific configuration steps.

    Each gateway implements this protocol to declare its configuration
    steps (connection, variant, etc.). The config flow orchestrator
    calls these methods generically without knowing the gateway type.

    Step IDs are arbitrary and gateway-owned, prefixed by the gateway
    identifier to avoid collisions (e.g., 'atw_mbs_02_connection').
    """

    def config_steps(self) -> list[str]:
        """Return ordered list of step IDs for this gateway."""
        ...

    def step_schema(
        self, step_id: str, context: dict[str, Any]
    ) -> StepSchema:
        """Return the form schema and placeholders for a step.

        Args:
            step_id: The step to get the schema for.
            context: Accumulated config data from previous steps.
        """
        ...

    async def process_step(
        self,
        hass: HomeAssistant,
        step_id: str,
        user_input: dict[str, Any],
        context: dict[str, Any],
    ) -> StepOutcome:
        """Process user input for a step.

        Args:
            hass: Home Assistant instance.
            step_id: The step being processed.
            user_input: Form data submitted by the user.
            context: Accumulated config data from previous steps.

        Returns:
            StepOutcome with errors (re-display form), config_data
            (accumulate into context), and/or detected_profiles
            (triggers transition to profile selection).
        """
        ...


# Provider registry — maps gateway_type to provider class.
# Import here to avoid circular imports; providers import from this module.
from .atw_mbs_02 import AtwMbs02ConfigProvider  # noqa: E402
from .hc_a_mb import HcAMbConfigProvider  # noqa: E402

GATEWAY_CONFIG_PROVIDERS: dict[str, type[GatewayConfigProvider]] = {
    "modbus_atw_mbs_02": AtwMbs02ConfigProvider,
    "modbus_hc_a_mb": HcAMbConfigProvider,
}
```

Note: The imports at the bottom will fail until Task 2 and Task 3 create the provider files. Create placeholder files first if needed.

- [ ] **Step 2: Verify the module structure**

```bash
mkdir -p custom_components/hitachi_yutaki/api/config_providers
touch custom_components/hitachi_yutaki/api/config_providers/__init__.py
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/hitachi_yutaki/api/config_providers/__init__.py
git commit -m "feat: add GatewayConfigProvider protocol and dataclasses

Protocol-based system where each gateway declares its own config flow
steps. Includes StepSchema, StepOutcome dataclasses and provider registry.

Refs: #248"
```

---

### Task 2: Create ATW-MBS-02 config provider

**Files:**
- Create: `custom_components/hitachi_yutaki/api/config_providers/atw_mbs_02.py`

This provider extracts all ATW-MBS-02-specific logic currently in config_flow.py: connection schema, connection testing, variant auto-detection, and profile detection.

- [ ] **Step 1: Create the provider**

The provider must:

1. Declare steps: `["atw_mbs_02_connection", "atw_mbs_02_variant"]`

2. `atw_mbs_02_connection` step:
   - Schema: host, port, device_id, scan_interval (same fields as current `GATEWAY_SCHEMA`)
   - Process: store connection params, test Modbus TCP connectivity (extract `_test_connection()` logic from config_flow.py lines 263-299)
   - On success: return config_data with connection params
   - On failure: return errors `{"base": "cannot_connect"}`

3. `atw_mbs_02_variant` step:
   - Schema: gen1/gen2 selector with LIST mode and `gateway_variant` translation_key
   - `step_schema()`: perform auto-detection (extract `_detect_variant()` logic from config_flow.py lines 301-352), set default and description_placeholders with detected variant and model_decoder_url
   - Process: store chosen variant, create register map, detect profiles (extract `_detect_and_store_profiles()` logic from config_flow.py lines 354-401)
   - On success: return config_data with gateway_variant + detected_profiles
   - On failure: return errors

Key imports needed:
- `GATEWAY_INFO` and `create_register_map` from `..`
- `GATEWAY_VARIANTS` from `..modbus.registers`
- `PROFILES` from `...profiles`
- Modbus/connection exceptions from pymodbus
- HA selector, vol, cv from homeassistant

Reference files:
- `config_flow.py` lines 158-401 (all the logic being extracted)
- `api/__init__.py` (GATEWAY_INFO, create_register_map)

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from custom_components.hitachi_yutaki.api.config_providers.atw_mbs_02 import AtwMbs02ConfigProvider; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/hitachi_yutaki/api/config_providers/atw_mbs_02.py
git commit -m "feat: add ATW-MBS-02 config provider

Extracts connection testing, variant auto-detection, and profile
detection from config_flow.py into a GatewayConfigProvider.

Steps: atw_mbs_02_connection, atw_mbs_02_variant

Refs: #248"
```

---

### Task 3: Create HC-A-MB config provider

**Files:**
- Create: `custom_components/hitachi_yutaki/api/config_providers/hc_a_mb.py`

Single step provider — connection with unit_id, plus profile detection.

- [ ] **Step 1: Create the provider**

The provider must:

1. Declare steps: `["hc_a_mb_connection"]`

2. `hc_a_mb_connection` step:
   - Schema: host, port, device_id, scan_interval, **unit_id** (the HC-A-MB-specific field, range 0-15)
   - Process: store connection params including unit_id, test connectivity, create register map (HC-A-MB uses unit_id for addressing), detect profiles
   - On success: return config_data with all params + detected_profiles
   - On failure: return errors

Reference: config_flow.py lines 176-179 (unit_id handling) and the same connection/profile detection logic.

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from custom_components.hitachi_yutaki.api.config_providers.hc_a_mb import HcAMbConfigProvider; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/hitachi_yutaki/api/config_providers/hc_a_mb.py
git commit -m "feat: add HC-A-MB config provider

Single step provider with unit_id support. Handles connection
testing and profile detection.

Steps: hc_a_mb_connection

Refs: #248"
```

---

### Task 4: Refactor config flow to use orchestrator

**Files:**
- Modify: `custom_components/hitachi_yutaki/config_flow.py`

This is the core refactoring. The config flow becomes a thin orchestrator.

- [ ] **Step 1: Update imports**

Replace:
```python
from .api import GATEWAY_INFO, create_register_map
from .api.modbus.registers import GATEWAY_VARIANTS
```

With:
```python
from .api import GATEWAY_INFO
from .api.config_providers import GATEWAY_CONFIG_PROVIDERS
```

Remove imports no longer needed: `create_register_map`, `GATEWAY_VARIANTS`, `CONF_UNIT_ID`, `DEFAULT_UNIT_ID`.

Remove module-level `GATEWAY_SCHEMA` (providers own their schemas now).

- [ ] **Step 2: Refactor `HitachiYutakiConfigFlow.__init__`**

Replace gateway-specific state with provider state:

```python
def __init__(self):
    """Initialize the config flow."""
    self.gateway_type: str | None = None
    self._provider: GatewayConfigProvider | None = None
    self._provider_steps: list[str] = []
    self._current_step_index: int = 0
    self._step_context: dict[str, Any] = {}
    self.detected_profiles: list[str] = []
```

- [ ] **Step 3: Refactor `async_step_user`**

After gateway selection, instantiate the provider and register dynamic step methods:

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
        # HA calls async_step_<step_id>() via introspection when a form
        # is submitted. Since provider step IDs are dynamic, we register
        # them at runtime. All route to the same _handle_provider_step.
        for step_id in self._provider_steps:
            setattr(self, f"async_step_{step_id}", self._handle_provider_step)

        # Show first provider step
        return await self._handle_provider_step()

    return self.async_show_form(
        step_id="user", data_schema=GATEWAY_SELECTION_SCHEMA
    )
```

- [ ] **Step 4: Add `_handle_provider_step`**

```python
async def _handle_provider_step(self, user_input=None):
    """Generic handler for all provider configuration steps.

    This method handles every step declared by the gateway's
    GatewayConfigProvider. HA routes to it via dynamically registered
    async_step_<step_id> methods (see async_step_user).

    Flow:
    1. First call (user_input=None): get schema from provider, show form
    2. Submission (user_input=dict): pass to provider's process_step()
       - If errors: re-show form
       - If ok: merge config_data into context, advance to next step
       - If last step: store detected_profiles, go to profile selection
    """
    step_id = self._provider_steps[self._current_step_index]

    if user_input is not None:
        outcome = await self._provider.process_step(
            self.hass, step_id, user_input, self._step_context
        )

        if outcome.errors:
            # Re-show current step with errors
            step_schema = self._provider.step_schema(step_id, self._step_context)
            return self.async_show_form(
                step_id=step_id,
                data_schema=step_schema.schema,
                description_placeholders=step_schema.description_placeholders,
                errors=outcome.errors,
            )

        # Accumulate config data
        if outcome.config_data:
            self._step_context.update(outcome.config_data)

        # Store detected profiles if provided
        if outcome.detected_profiles is not None:
            self.detected_profiles = outcome.detected_profiles

        # Advance to next step or exit to profile selection
        self._current_step_index += 1
        if self._current_step_index >= len(self._provider_steps):
            return await self.async_step_profile()

        # Show next step (fall through to form display below)
        step_id = self._provider_steps[self._current_step_index]

    # Show form for current step
    step_schema = self._provider.step_schema(step_id, self._step_context)
    return self.async_show_form(
        step_id=step_id,
        data_schema=step_schema.schema,
        description_placeholders=step_schema.description_placeholders,
    )
```

- [ ] **Step 5: Remove old gateway-specific methods and helpers**

Delete:
- `async_step_gateway_config` (replaced by `_handle_provider_step`)
- `async_step_gateway_variant` (replaced by `_handle_provider_step`)
- `_test_connection()` (moved to providers)
- `_detect_variant()` (moved to ATW-MBS-02 provider)
- `_detect_and_store_profiles()` (moved to providers)
- `GATEWAY_SCHEMA` module-level constant

- [ ] **Step 6: Update `async_step_power` to use context**

The power step currently references `self.gateway_type` and `self.gateway_variant`. Update to use `self._step_context`:

```python
async def async_step_power(self, user_input=None):
    if user_input is not None:
        config = {
            "gateway_type": self.gateway_type,
            **self._step_context,
            **user_input,
        }
        return await self.async_validate_connection(config)
    # ... rest unchanged
```

- [ ] **Step 7: Update `async_validate_connection`**

This method needs `create_register_map` — import it locally or keep the import. The function still needs gateway_type, variant, and connection params, all of which are in the config dict.

- [ ] **Step 8: Refactor the Options Flow**

Apply the same pattern:
- `async_step_init`: after gateway selection, instantiate provider, register step methods, go to first provider step
- Add `_handle_provider_step` (same logic, but after all provider steps go to `async_step_profile` instead of `async_step_profile`)
- Remove `async_step_connection` and `async_step_gateway_variant` (replaced by provider steps)
- `async_step_profile` and `async_step_sensors` stay unchanged

The options flow provider needs current config entry data to pre-fill defaults. Pass `self.config_entry.data` as initial context.

- [ ] **Step 9: Run `make check`**

- [ ] **Step 10: Commit**

```bash
git add custom_components/hitachi_yutaki/config_flow.py
git commit -m "refactor: replace gateway-specific config flow with provider orchestrator

The config flow now delegates to GatewayConfigProvider instances.
Dynamic setattr registration bridges HA step routing to a single
generic handler. No gateway-specific logic remains in config_flow.py.

Refs: #248"
```

---

### Task 5: Update translations

**Files:**
- Modify: `custom_components/hitachi_yutaki/translations/en.json`
- Modify: `custom_components/hitachi_yutaki/translations/fr.json`
- Modify: `custom_components/hitachi_yutaki/translations/nl.json`
- Modify: `custom_components/hitachi_yutaki/translations/ro.json`

- [ ] **Step 1: Rename step keys in all 4 files**

In both `config.step` and `options.step` sections:

| Old key | New key | Notes |
|---------|---------|-------|
| `gateway_config` | `atw_mbs_02_connection` | ATW-MBS-02 connection step |
| `gateway_variant` | `atw_mbs_02_variant` | ATW-MBS-02 variant step |
| `connection` (options) | `atw_mbs_02_connection` | Shared with config flow |

Add new key:
| New key | Notes |
|---------|-------|
| `hc_a_mb_connection` | HC-A-MB connection step (includes unit_id field) |

The `hc_a_mb_connection` step needs `data.unit_id` label in addition to the standard connection fields.

Remove `gateway_variant` from `selector` section (the variant selector is now managed by the provider's schema with `translation_key`).

Keep `gateway_type` selector unchanged.

- [ ] **Step 2: Run `make check`**

- [ ] **Step 3: Commit**

```bash
git add custom_components/hitachi_yutaki/translations/
git commit -m "feat: rename translation keys for provider-based config flow

Step IDs now use gateway-prefixed names matching the providers:
atw_mbs_02_connection, atw_mbs_02_variant, hc_a_mb_connection.

Refs: #248"
```

---

### Task 6: Update tests

**Files:**
- Create: `tests/api/config_providers/__init__.py`
- Create: `tests/api/config_providers/test_atw_mbs_02.py`
- Create: `tests/api/config_providers/test_hc_a_mb.py`
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Create provider unit tests**

For `test_atw_mbs_02.py`:
- `test_config_steps_returns_two_steps` — verify order: connection, variant
- `test_connection_step_schema` — verify schema has host/port/device_id/scan_interval
- `test_variant_step_schema_has_gen_options` — verify gen1/gen2 in schema
- `test_connection_process_success` — mock hass, verify config_data returned
- `test_connection_process_failure` — verify errors returned
- `test_variant_process_detects_profiles` — verify detected_profiles in outcome

For `test_hc_a_mb.py`:
- `test_config_steps_returns_one_step` — single connection step
- `test_connection_step_schema_has_unit_id` — verify unit_id field in schema
- `test_connection_process_success_with_profiles` — verify config_data + detected_profiles

- [ ] **Step 2: Update `test_config_flow.py`**

Update helper functions and tests:
- Replace `_advance_to_gateway_config()` with `_advance_to_provider_step(step_id)`
- Update step_id assertions to use new prefixed names
- Patch `GATEWAY_CONFIG_PROVIDERS` instead of `GATEWAY_INFO` where needed
- Update the advance functions to follow the new flow: user → first_provider_step → ... → profile → power

- [ ] **Step 3: Run full test suite**

```bash
make test
```

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: add provider unit tests and update config flow tests

Unit tests for ATW-MBS-02 and HC-A-MB providers. Config flow tests
updated for provider-based step routing.

Refs: #248"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run full test suite**

```bash
make test
```

- [ ] **Step 2: Run lint**

```bash
make check
```

- [ ] **Step 3: Verify hassfest**

The CI will run hassfest. Verify locally if possible that translation keys are valid (no raw URLs, all step_id keys have translations).

- [ ] **Step 4: Push**

```bash
git push
```

---

## Verification Checklist

- [ ] `GatewayConfigProvider` protocol with `StepSchema` and `StepOutcome` dataclasses
- [ ] `AtwMbs02ConfigProvider` with connection + variant steps
- [ ] `HcAMbConfigProvider` with connection step (includes unit_id)
- [ ] Config flow orchestrator uses `setattr` + `_handle_provider_step`
- [ ] No gateway-specific `if` statements remain in config_flow.py
- [ ] Options flow uses same provider pattern
- [ ] Translations use gateway-prefixed step IDs
- [ ] Hassfest passes (no raw URLs in translations)
- [ ] Provider unit tests pass
- [ ] Config flow integration tests pass
- [ ] `make test` — all tests pass
- [ ] `make check` — lint clean
