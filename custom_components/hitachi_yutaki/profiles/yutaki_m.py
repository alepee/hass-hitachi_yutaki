"""Profile for the Hitachi Yutaki M heat pump."""

from typing import Any

from ..const import UNIT_MODEL_M
from .base import HitachiHeatPumpProfile


class YutakiMProfile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutaki M heat pump."""

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == UNIT_MODEL_M

    @property
    def supports_dhw(self) -> bool:
        """Return True if the heat pump supports Domestic Hot Water."""
        return False
