"""Profile for the Hitachi Yutaki M heat pump."""

from typing import Any

from .base import HitachiHeatPumpProfile


class YutakiMProfile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutaki M monobloc heat pump.

    Monobloc system (outdoor unit only, no indoor unit).
    - 2 circuits supported
    - No integrated DHW, but external tank compatible
    - Cooling built-in (no kit needed)
    - Water outlet up to 60°C
    - Operating range: -25°C to +46°C outdoor
    - Twin-rotary compressor with vapor injection
    """

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == "yutaki_m"

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "Yutaki M"

    @property
    def dhw_min_temp(self) -> int | None:
        """Return minimum DHW temperature in °C."""
        return 30

    @property
    def dhw_max_temp(self) -> int | None:
        """Return maximum DHW temperature in °C (heat pump only).

        Per Hitachi docs: 57°C max (53°C for 2.0-3.0HP), 55°C recommended.
        """
        return 55

    @property
    def max_circuits(self) -> int:
        """Return maximum number of circuits."""
        return 2

    @property
    def supports_cooling(self) -> bool:
        """Return True - cooling is built-in (no kit needed)."""
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
