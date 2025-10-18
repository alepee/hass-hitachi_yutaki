"""Profile for the Hitachi Yutaki S Combi heat pump."""

from typing import Any

from .base import HitachiHeatPumpProfile


class YutakiSCombiProfile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutaki S Combi heat pump."""

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == "yutaki_s_combi"

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "Yutaki S Combi"
