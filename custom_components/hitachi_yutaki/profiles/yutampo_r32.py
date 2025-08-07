"""Yutampo R32 profile implementation.

Represents a domestic hot water (DHW) only heat pump unit. No space heating/cooling circuits.
"""

from __future__ import annotations

from typing import Iterable

from . import HitachiHeatPumpProfile


class YutampoR32Profile(HitachiHeatPumpProfile):
    @property
    def model_key(self) -> str:
        return "yutampo_r32"

    @property
    def name(self) -> str:
        return "Yutampo R32"

    @property
    def supports_dhw(self) -> bool:
        # Yutampo is a DHW-only product
        return True

    @property
    def supports_pool(self) -> bool:
        # Pool not supported on Yutampo
        return False

    @property
    def supports_circuit1_heating(self) -> bool:
        return False

    @property
    def supports_circuit1_cooling(self) -> bool:
        return False

    @property
    def supports_circuit2_heating(self) -> bool:
        return False

    @property
    def supports_circuit2_cooling(self) -> bool:
        return False

    def extra_register_keys(self) -> Iterable[str]:
        # No extra protocol-agnostic keys beyond the standard map for DHW
        return ()

