"""Profile for the Hitachi YCC (Yutaki Commercial Controller)."""

from typing import Any

from .base import HitachiHeatPumpProfile


class YccProfile(HitachiHeatPumpProfile):
    """Profile for the Hitachi YCC.

    YCC is reported as unit_model=6 by HC-A16MB.
    Starting with minimal/default capabilities; refine as documentation
    and user feedback become available.
    """

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == "ycc"

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "YCC"

    @property
    def max_circuits(self) -> int:
        """Return maximum number of circuits."""
        return 2

    @property
    def supports_cooling(self) -> bool:
        """Return True - cooling supported."""
        return True

    @property
    def supports_pool(self) -> bool:
        """Return True - pool heating supported."""
        return True

    @property
    def supports_boiler(self) -> bool:
        """Return True - backup boiler supported."""
        return True
