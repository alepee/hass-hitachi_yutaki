"""Profile for the Hitachi Yutaki SC Lite heat pump."""

from typing import Any

from .base import HitachiHeatPumpProfile


class YutakiScLiteProfile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutaki SC Lite heat pump.

    Variant of the S Combi line, reported as unit_model=4 by HC-A(16/64)MB.
    Starting with S Combi-like capabilities; refine as more data is available.
    """

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == "yutaki_sc_lite"

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "Yutaki SC Lite"

    @property
    def dhw_min_temp(self) -> int | None:
        """Return minimum DHW temperature in °C."""
        return 30

    @property
    def dhw_max_temp(self) -> int | None:
        """Return maximum DHW temperature in °C (heat pump only)."""
        return 55

    @property
    def max_circuits(self) -> int:
        """Return maximum number of circuits."""
        return 1

    @property
    def supports_cooling(self) -> bool:
        """Return True - cooling supported."""
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
