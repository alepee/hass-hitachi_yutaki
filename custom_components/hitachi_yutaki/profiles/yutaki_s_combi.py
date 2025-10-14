"""Profile for the Hitachi Yutaki S Combi heat pump."""

from typing import Any

from ..const import UNIT_MODEL_YUTAKI_S_COMBI
from .base import HitachiHeatPumpProfile


class YutakiSCombiProfile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutaki S Combi heat pump."""

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == UNIT_MODEL_YUTAKI_S_COMBI
