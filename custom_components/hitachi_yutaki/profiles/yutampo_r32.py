"""Profile for the Hitachi Yutampo R32 heat pump."""

from typing import Any

from .base import HitachiHeatPumpProfile


class YutampoR32Profile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutampo R32 DHW-only heat pump.

    Split DHW-dedicated system.
    - NO heating/cooling circuits (DHW only)
    - Integrated DHW tank 190L or 270L (stainless steel)
    - DHW max 55°C by heat pump, 75°C with electric resistance
    - Heating time: 3h (190L), 3.5h (270L)
    - Detection: unit_model=1 (S Combi) + no circuits configured
    """

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected.

        Detection works via two paths:
        - Direct match: HC-A16MB reports unit_model="yutampo" directly.
        - Heuristic match: ATW-MBS-02 reports unit_model="yutaki_s_combi"
          but with DHW only and no heating/cooling circuits configured.
        """
        unit_model = data.get("unit_model")
        # Direct match (HC-A16MB provides exact model)
        if unit_model == "yutampo_r32":
            return True
        # Heuristic match (ATW-MBS-02 reports S Combi, infer from config)
        return (
            unit_model == "yutaki_s_combi"
            and data.get("has_dhw") is True
            and not data.get("has_circuit1_heating")
            and not data.get("has_circuit1_cooling")
            and not data.get("has_circuit2_heating")
            and not data.get("has_circuit2_cooling")
        )

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "Yutampo R32"

    @property
    def dhw_min_temp(self) -> int | None:
        """Return minimum DHW temperature in °C."""
        return 30

    @property
    def dhw_max_temp(self) -> int | None:
        """Return maximum DHW temperature in °C (heat pump only).

        55°C by heat pump, 75°C achievable with electric resistance.
        """
        return 55

    @property
    def max_circuits(self) -> int:
        """Return 0 - Yutampo R32 is DHW-only, no heating/cooling circuits."""
        return 0

    @property
    def supports_cooling(self) -> bool:
        """Return False - DHW-only unit, no cooling capability."""
        return False

    @property
    def supports_pool(self) -> bool:
        """Return False - DHW-only unit, no pool heating."""
        return False

    @property
    def supports_boiler(self) -> bool:
        """Return False - no backup boiler support."""
        return False

    @property
    def entity_overrides(self) -> dict:
        """Return entity overrides for the profile.

        Includes boost_temp for electric resistance heating.
        """
        return {
            "water_heater": {
                "min_temp": 30,
                "max_temp": 55,
                "boost_temp": 75,
            }
        }
