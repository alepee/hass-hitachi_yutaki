"""Profile for the Hitachi Yutaki S Combi heat pump."""

from typing import Any

from .base import HitachiHeatPumpProfile


class YutakiSCombiProfile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutaki S Combi heat pump.

    Split system with integrated 220L DHW tank.
    - 1 circuit by default (2nd zone possible with mixing kit ATW-2KT-03)
    - Integrated DHW, max 55°C recommended (57°C absolute by HP, 60°C with resistance)
    - Cooling with optional kit
    - Water outlet up to 60°C
    - Operating range: -25°C to +46°C outdoor
    """

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected.

        S Combi requires at least one heating or cooling circuit configured.
        If unit_model=1 but no circuits, it's a Yutampo R32 (DHW-only).
        """
        has_any_circuit = (
            data.get("has_circuit1_heating")
            or data.get("has_circuit1_cooling")
            or data.get("has_circuit2_heating")
            or data.get("has_circuit2_cooling")
        )
        return data.get("unit_model") == "yutaki_s_combi" and has_any_circuit

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "Yutaki S Combi"

    @property
    def dhw_min_temp(self) -> int | None:
        """Return minimum DHW temperature in °C."""
        return 30

    @property
    def dhw_max_temp(self) -> int | None:
        """Return maximum DHW temperature in °C (heat pump only).

        Integrated 220L tank. 57°C absolute max by HP, 55°C recommended.
        60°C possible with electric resistance.
        """
        return 55

    @property
    def max_circuits(self) -> int:
        """Return maximum circuits.

        S Combi has 1 circuit by default. A 2nd zone is possible
        with the mixing kit ATW-2KT-03, but max remains 1 for base model.
        """
        return 1

    @property
    def supports_cooling(self) -> bool:
        """Return True - cooling supported with optional kit."""
        return True

    @property
    def max_water_outlet_temp(self) -> int:
        """Return maximum water outlet temperature in °C."""
        return 60

    @property
    def supports_pool(self) -> bool:
        """Return True - pool heating supported."""
        return True

    @property
    def supports_boiler(self) -> bool:
        """Return True - backup boiler supported."""
        return True
