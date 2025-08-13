"""Yutaki S80 profile implementation.

Encodes model-specific capabilities and extra keys for the S80 variant.
"""

from __future__ import annotations

from collections.abc import Iterable

from .base import HitachiHeatPumpProfile


class YutakiS80Profile(HitachiHeatPumpProfile):
    """Profile for Hitachi Yutaki S80 models."""

    @property
    def model_key(self) -> str:
        """Canonical model key for this profile."""
        return "yutaki_s80"

    @property
    def name(self) -> str:
        """Human-readable model name."""
        return "Yutaki S80"

    @property
    def supports_dhw(self) -> bool:
        """Whether DHW is supported by the model family."""
        return True

    @property
    def supports_pool(self) -> bool:
        """Whether pool mode is allowed by the model family."""
        return True

    def entity_overrides(
        self, register_key: str, platform: str, coordinator
    ) -> dict | None:
        """Return platform-specific overrides for a given logical register key.

        For S80, we keep defaults and only gate entity creation where needed.
        """
        if platform == "water_heater" and register_key == "dhw":
            # Respect gateway/config DHW presence
            if not getattr(coordinator, "has_dhw", lambda: False)():
                return None
            # No special UI limits here; use platform defaults
            return {}

        # Unknown keys/platforms: no special handling
        return {}

    @property
    def supports_circuit1(self) -> bool:
        """Whether circuit 1 is supported by the model family."""
        return True

    @property
    def supports_circuit2(self) -> bool:
        """Whether circuit 2 is supported by the model family."""
        return True

    def extra_register_keys(self) -> Iterable[str]:
        """Additional logical register keys required by this profile.

        Coordinator already handles model == S80 for R134a keys, but providing
        this here enables a future move where coordinator asks profile.
        """
        return (
            "r134a_discharge_temp",
            "r134a_suction_temp",
            "r134a_discharge_pressure",
            "r134a_suction_pressure",
            "r134a_compressor_frequency",
            "r134a_valve_opening",
            "r134a_compressor_current",
            "r134a_retry_code",
            "r134a_hp_pressure",
            "r134a_lp_pressure",
        )
