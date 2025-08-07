"""Yutaki S Combi profile implementation.

Encodes model-specific capabilities and rules for the Yutaki S Combi variant.
"""

from __future__ import annotations

from typing import Iterable

from . import HitachiHeatPumpProfile


class YutakiSCombiProfile(HitachiHeatPumpProfile):
    @property
    def model_key(self) -> str:
        return "yutaki_s_combi"

    @property
    def name(self) -> str:
        return "Yutaki S Combi"

    @property
    def supports_dhw(self) -> bool:
        # Combi models include integrated DHW cylinder
        return True

    @property
    def supports_pool(self) -> bool:
        # Pool support depends on system configuration; profile allows it
        return True

    @property
    def supports_circuit1_heating(self) -> bool:
        return True

    @property
    def supports_circuit1_cooling(self) -> bool:
        return True

    @property
    def supports_circuit2_heating(self) -> bool:
        return True

    @property
    def supports_circuit2_cooling(self) -> bool:
        return True

    def extra_register_keys(self) -> Iterable[str]:
        # No additional protocol-agnostic keys required beyond the standard map
        return ()

