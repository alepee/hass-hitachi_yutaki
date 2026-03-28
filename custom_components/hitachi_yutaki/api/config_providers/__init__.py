"""Gateway configuration providers.

Each gateway type implements the GatewayConfigProvider protocol to declare
its own configuration steps. The config flow orchestrator iterates over
these steps generically, without knowing the gateway type in advance.

Architecture
------------
- The config flow (config_flow.py) is a thin orchestrator.
- Each gateway owns its steps: step IDs, schemas, and processing logic.
- Both the initial config flow and the options flow consume the same provider.

Step ID convention
------------------
Step IDs are prefixed by the gateway identifier to avoid collisions and to
make translations explicit. Examples:

    ATW-MBS-02:  ["atw_mbs_02_connection", "atw_mbs_02_variant"]
    HC-A-MB:     ["hc_a_mb_connection"]

HA step routing
---------------
Home Assistant dispatches form submissions by calling async_step_<step_id>()
via introspection. Since provider step IDs are dynamic (declared at runtime),
the config flow registers them on the instance using setattr, pointing to a
single _handle_provider_step() handler. This preserves standard HA routing
while keeping the orchestrator generic.

Translation convention
----------------------
Translations must live under the standard HA paths, using the provider's
step IDs:

    config.step.<step_id>.title
    config.step.<step_id>.description
    config.step.<step_id>.data.<field>
    options.step.<step_id>.title  (etc.)

Both config and options flows use the SAME step IDs from the provider,
so translations are shared.

Adding a new gateway
--------------------
1. Create api/config_providers/my_gateway.py implementing GatewayConfigProvider
2. Choose gateway-prefixed step IDs (e.g., "my_gateway_connection")
3. Add translations under config.step.<step_id> and options.step.<step_id>
4. Register in GATEWAY_CONFIG_PROVIDERS below
5. Add GatewayInfo entry in api/__init__.py
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

    Attributes:
        errors: Validation errors to re-display the form.
            Keys match schema field names or "base" for general errors.
        config_data: Data to accumulate into the flow context.
            Subsequent steps can read these values from the context dict.
        detected_profiles: Heat pump profile keys detected from the gateway.
            Set by the provider's last step to trigger profile selection.

    """

    errors: dict[str, str] | None = None
    config_data: dict[str, Any] | None = None
    detected_profiles: list[str] | None = None


class GatewayConfigProvider(Protocol):
    """Protocol for gateway-specific configuration steps.

    Each gateway implements this to declare its configuration steps
    (connection, variant, etc.). The config flow orchestrator calls
    these methods generically without knowing the gateway type.
    """

    def config_steps(self) -> list[str]:
        """Return ordered list of step IDs for this gateway.

        Step IDs must be prefixed by the gateway identifier
        (e.g., "atw_mbs_02_connection", "hc_a_mb_connection").
        """
        ...

    def step_schema(self, step_id: str, context: dict[str, Any]) -> StepSchema:
        """Return the form schema and description placeholders for a step.

        Args:
            step_id: The step to get the schema for.
            context: Accumulated config data from previous steps.
                     Empty dict for the first step, then grows as each
                     step's config_data is merged in.

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
            hass: Home Assistant instance (for creating API clients, etc.).
            step_id: The step being processed.
            user_input: Form data submitted by the user.
            context: Accumulated config data from previous steps.

        Returns:
            StepOutcome with errors (re-display form), config_data
            (accumulate into context), and/or detected_profiles
            (triggers transition to profile selection).

        """
        ...


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------
# Imports at the bottom to avoid circular dependencies.
# Each provider module imports from this package (StepSchema, StepOutcome).

from .atw_mbs_02 import AtwMbs02ConfigProvider  # noqa: E402
from .hc_a_mb import HcAMbConfigProvider  # noqa: E402

GATEWAY_CONFIG_PROVIDERS: dict[str, type[GatewayConfigProvider]] = {
    "modbus_atw_mbs_02": AtwMbs02ConfigProvider,
    "modbus_hc_a_mb": HcAMbConfigProvider,
}
