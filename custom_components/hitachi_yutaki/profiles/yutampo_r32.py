"""Profile for the Hitachi Yutampo R32 heat pump."""

from typing import Any

from ..const import MASK_CIRCUIT1_HEATING, UNIT_MODEL_YUTAKI_S_COMBI
from .base import HitachiHeatPumpProfile


class YutampoR32Profile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutampo R32 heat pump."""

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == UNIT_MODEL_YUTAKI_S_COMBI and not (
            data.get("system_config", 0) & MASK_CIRCUIT1_HEATING
        )

    @property
    def supports_circuit1(self) -> bool:
        """Return True if the heat pump supports heating circuit 1."""
        return False

    @property
    def supports_circuit2(self) -> bool:
        """Return True if the heat pump supports heating circuit 2."""
        return False

    @property
    def entity_overrides(self) -> dict:
        """Return entity overrides for the profile."""
        return {
            "water_heater": {
                "min_temp": 30,
                "max_temp": 55,
                "boost_temp": 75,
            }
        }
