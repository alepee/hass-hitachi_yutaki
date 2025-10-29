"""Profile for the Hitachi Yutampo R32 heat pump."""

from typing import Any

from .base import HitachiHeatPumpProfile


class YutampoR32Profile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutampo R32 heat pump."""

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return (
            data.get("unit_model") == "yutampo_r32"
            and data.get("has_dhw")
            and not data.get("has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING)")
            and not data.get("has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING)")
        )

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "Yutampo R32"

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
