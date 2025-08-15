"""Yutaki S profile implementation.

Encodes model-specific capabilities and rules for the Yutaki S variant.
"""

from __future__ import annotations

from collections.abc import Iterable

from .base import HitachiHeatPumpProfile


class YutakiSProfile(HitachiHeatPumpProfile):
    """Profile for Hitachi Yutaki S models."""

    @property
    def model_key(self) -> str:
        """Canonical model key for this profile."""
        return "yutaki_s"

    @property
    def name(self) -> str:
        """Human-readable model name."""
        return "Yutaki S"

    @property
    def supports_dhw(self) -> bool:
        """Whether DHW is supported by the model family."""
        return True

    @property
    def supports_pool(self) -> bool:
        """Whether pool mode is allowed by the model family."""
        return True

    @property
    def supports_circuit1(self) -> bool:
        """Whether circuit 1 is supported by the model family."""
        return True

    @property
    def supports_circuit2(self) -> bool:
        """Whether circuit 2 is supported by the model family."""
        return True

    def extra_register_keys(self) -> Iterable[str]:
        """Additional logical register keys required by this profile."""
        return ()
