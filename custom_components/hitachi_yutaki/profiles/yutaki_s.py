"""Profile for the Hitachi Yutaki S heat pump."""

from typing import Any

from .base import HitachiHeatPumpProfile


class YutakiSProfile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutaki S heat pump."""

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == "yutaki_s"

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "Yutaki S"
