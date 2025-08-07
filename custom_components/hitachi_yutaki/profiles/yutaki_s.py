"""Yutaki S profile implementation.

Encodes model-specific capabilities and rules for the Yutaki S variant.
"""

from __future__ import annotations

from typing import Iterable

from . import HitachiHeatPumpProfile


class YutakiSProfile(HitachiHeatPumpProfile):
    @property
    def model_key(self) -> str:
        return "yutaki_s"

    @property
    def name(self) -> str:
        return "Yutaki S"

    @property
    def supports_dhw(self) -> bool:
        # Yutaki S typically supports DHW (direct or via external tank)
        # Final availability still depends on configuration bits and gateway caps
        return True

    @property
    def supports_pool(self) -> bool:
        # Pool support depends on system configuration; profile allows it
        return True

    @property
    def supports_circuit1_heating(self) -> bool:
        # Allow circuit 1 heating; final availability depends on gateway/config
        return True

    @property
    def supports_circuit1_cooling(self) -> bool:
        # Allow circuit 1 cooling; final availability depends on gateway/config
        return True

    @property
    def supports_circuit2_heating(self) -> bool:
        # Allow circuit 2 heating; final availability depends on gateway/config
        return True

    @property
    def supports_circuit2_cooling(self) -> bool:
        # Allow circuit 2 cooling; final availability depends on gateway/config
        return True

    def extra_register_keys(self) -> Iterable[str]:
        # No additional protocol-agnostic keys required beyond the standard map
        return ()

