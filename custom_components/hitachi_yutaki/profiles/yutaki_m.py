"""Profile for the Hitachi Yutaki M heat pump."""

from typing import Any

from .base import HitachiHeatPumpProfile


class YutakiMProfile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutaki M heat pump."""

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == "yutaki_m"

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "Yutaki M"

    @property
    def supports_dhw(self) -> bool:
        """Return True if the heat pump supports Domestic Hot Water."""
        return False
