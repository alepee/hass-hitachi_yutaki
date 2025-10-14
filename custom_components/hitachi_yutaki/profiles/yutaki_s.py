"""Profile for the Hitachi Yutaki S heat pump."""

from typing import Any

from ..const import UNIT_MODEL_YUTAKI_S
from .base import HitachiHeatPumpProfile


class YutakiSProfile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutaki S heat pump."""

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == UNIT_MODEL_YUTAKI_S
