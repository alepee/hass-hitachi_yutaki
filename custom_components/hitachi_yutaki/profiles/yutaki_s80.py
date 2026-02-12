"""Profile for the Hitachi Yutaki S80 heat pump."""

from __future__ import annotations

from typing import Any

from .base import HitachiHeatPumpProfile


class YutakiS80Profile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Yutaki S80 high-temperature heat pump.

    Split high-temperature system.
    - 2 circuits supported
    - Integrated or external DHW (200L/260L options), max 75°C by HP alone
    - NO cooling capability (heating only)
    - Water outlet up to 80°C even at -20°C outdoor
    - Cascade compressor: R410A + R134a (boosts 45°C → 80°C)
    - Designed for oil boiler replacement, high-temp radiators
    """

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == "yutaki_s80"

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "Yutaki S80"

    @property
    def dhw_min_temp(self) -> int | None:
        """Return minimum DHW temperature in °C."""
        return 30

    @property
    def dhw_max_temp(self) -> int | None:
        """Return maximum DHW temperature.

        S80 can reach 75°C for DHW by heat pump alone (no electric boost needed).
        Per manual PMFR0648 rev.0 - 03/2023, §4.2: DHW range 30-75°C.
        """
        return 75

    @property
    def max_circuits(self) -> int:
        """Return maximum number of circuits."""
        return 2

    @property
    def supports_cooling(self) -> bool:
        """Return False - S80 is heating only, no cooling capability."""
        return False

    @property
    def max_water_outlet_temp(self) -> int:
        """Return maximum water outlet temperature.

        S80 can reach 80°C water outlet even at -20°C outdoor temperature.
        """
        return 80

    @property
    def supports_high_temperature(self) -> bool:
        """Return True - S80 is a high-temperature model."""
        return True

    @property
    def supports_secondary_compressor(self) -> bool:
        """Return True if the heat pump has a secondary compressor."""
        return True

    @property
    def supports_boiler(self) -> bool:
        """Return False - S80 does not support backup boiler."""
        return False

    @property
    def supports_pool(self) -> bool:
        """Return True - pool heating supported (24-33°C range)."""
        return True

    @property
    def extra_register_keys(self) -> list[str]:
        """Return a list of extra register keys required by the profile."""
        return [
            "secondary_compressor_discharge_temp",
            "secondary_compressor_suction_temp",
            "secondary_compressor_discharge_pressure",
            "secondary_compressor_suction_pressure",
            "secondary_compressor_frequency",
            "secondary_compressor_valve_opening",
            "secondary_compressor_current",
            "secondary_compressor_retry_code",
            "secondary_compressor_hp_pressure",
            "secondary_compressor_lp_pressure",
        ]
