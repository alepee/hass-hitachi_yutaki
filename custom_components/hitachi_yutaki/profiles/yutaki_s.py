"""Profile for the Hitachi Yutaki S heat pump."""

from typing import Any

from .base import HitachiHeatPumpProfile


class YutakiSProfile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutaki S heat pump.

    Split system (indoor + outdoor units).
    - 2 circuits supported (Circuit 1 direct high temp, Circuit 2 mixing)
    - No integrated DHW, but external tank (DHWT-200/300S) compatible
    - Cooling with optional kit (ATW-CK-01)
    - Water outlet up to 60°C
    - Operating range: -25°C to +46°C outdoor
    """

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == "yutaki_s"

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "Yutaki S"

    @property
    def dhw_min_temp(self) -> int | None:
        """Return minimum DHW temperature in °C."""
        return 30

    @property
    def dhw_max_temp(self) -> int | None:
        """Return maximum DHW temperature in °C (heat pump only).

        Same as other standard models: 57°C max, 55°C recommended.
        """
        return 55

    @property
    def max_circuits(self) -> int:
        """Return maximum number of circuits."""
        return 2

    @property
    def supports_cooling(self) -> bool:
        """Return True - cooling supported with optional kit ATW-CK-01."""
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

    @property
    def gas_superheat_plausible_range(self) -> tuple[float, float]:
        """Return the (min, max) gas-line superheat plausibility bounds (K).

        Observed fleet band: ~44 K (25-51). Provisional single fleet-wide range;
        re-evaluate per model after the Jan-Feb 2027 winter re-run of
        backend/analysis/.
        """
        return (-10.0, 80.0)

    @property
    def gas_superheat_observed_band(self) -> tuple[float, float] | None:
        """Return the observed fleet band of frozen-baseline gas-line superheat."""
        return (25.0, 51.0)
