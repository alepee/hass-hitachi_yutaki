"""Yutampo R32 profile implementation.

Represents a domestic hot water (DHW) only heat pump unit. No space heating/cooling circuits.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .base import HitachiHeatPumpProfile


class YutampoR32Profile(HitachiHeatPumpProfile):
    """Profile for the DHW-only Hitachi Yutampo R32 unit."""

    @property
    def model_key(self) -> str:
        """Canonical model key for this profile."""
        return "yutampo_r32"

    @property
    def name(self) -> str:
        """Human-readable model name."""
        return "Yutampo R32"

    @property
    def supports_dhw(self) -> bool:
        """Whether DHW is supported (always true for Yutampo)."""
        return True

    @property
    def supports_pool(self) -> bool:
        """Whether pool mode is supported (not for Yutampo)."""
        return False

    @property
    def supports_circuit1(self) -> bool:
        """Whether circuit 1 is supported by the model family (not for Yutampo)."""
        return False

    @property
    def supports_circuit2(self) -> bool:
        """Whether circuit 2 is supported by the model family (not for Yutampo)."""
        return False

    def extra_register_keys(self) -> Iterable[str]:
        """Additional logical register keys required by this profile."""
        return ()

    def entity_overrides(
        self, register_key: str, platform: str, coordinator
    ) -> dict | None:
        """Return platform-specific overrides for a given logical register key.

        - Return None to indicate the entity should not be created.
        - Return a dict of key=value pairs to pass to the entity/description.

        This implementation only handles the DHW water_heater for Yutampo R32.
        """
        if platform == "water_heater" and register_key == "dhw":
            # Gate on DHW capability and gateway/config state
            if not getattr(coordinator, "has_dhw", lambda: False)():
                return None

            data: dict[str, Any] = coordinator.data or {}
            # Detect boost status directly from data (1 = active)
            value = data.get("boost") if isinstance(data, dict) else None
            try:
                boost_active = bool(int(value) == 1)
            except (TypeError, ValueError):
                boost_active = False

            # Inline policy: min 30°C, max 55°C normal, 75°C in boost, step 1°C
            min_temp = 30
            max_temp = 75 if boost_active else 55
            step = 1

            return {
                # Water heater temperature UI constraints
                "min_temp": min_temp,
                "max_temp": max_temp,
                "target_temperature_step": step,
                # Keep enabled by default
                "entity_registry_enabled_default": True,
            }

        # Unknown key/platform for this profile: no special handling
        return {}
