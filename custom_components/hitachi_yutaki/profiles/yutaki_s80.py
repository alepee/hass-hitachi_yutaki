"""Yutaki S80 profile implementation.

Encodes model-specific capabilities and extra keys for the S80 variant.
"""

from __future__ import annotations

from typing import Iterable

from . import HitachiHeatPumpProfile


class YutakiS80Profile(HitachiHeatPumpProfile):
    @property
    def model_key(self) -> str:
        return "yutaki_s80"

    @property
    def name(self) -> str:
        return "Yutaki S80"

    @property
    def supports_dhw(self) -> bool:
        # S80 supports DHW
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
        # Coordinator already handles model == S80 for R134a keys, but providing
        # this here enables a future move where coordinator asks profile.
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
