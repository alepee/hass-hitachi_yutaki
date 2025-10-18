"""Profile for the Hitachi Yutaki S80 heat pump."""

from __future__ import annotations

from typing import Any

from .base import HitachiHeatPumpProfile


class YutakiS80Profile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutaki S80 heat pump."""

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == "yutaki_s80"

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "Yutaki S80"

    @property
    def supports_secondary_compressor(self) -> bool:
        """Return True if the heat pump has a secondary compressor."""
        return True

    @property
    def supports_boiler(self) -> bool:
        """Return True if the heat pump has a backup boiler."""
        return False

    @property
    def extra_register_keys(self) -> list[str]:
        """Return a list of extra register keys required by the profile."""
        return [
            "secondary_compressor_discharge_temp",
            "secondary_compressor_suction_temp",
            "secondary_compressor_discharge_pressure",
            "secondary_compressor_suction_pressure",
            "secondary_compressor_frequency",
            "secondary_compressor_valve_opening",
            "secondary_compressor_current",
            "secondary_compressor_retry_code",
            "secondary_compressor_hp_pressure",
            "secondary_compressor_lp_pressure",
        ]
