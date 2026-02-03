"""Base profile for Hitachi heat pumps."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class HitachiHeatPumpProfile(ABC):
    """Abstract base class for a Hitachi Heat Pump profile.

    A profile defines the capabilities of a specific heat pump model,
    such as its support for Domestic Hot Water (DHW), swimming pools,
    or multiple heating circuits. It can also specify model-specific
    entity overrides or extra register keys required for its operation.
    """

    @staticmethod
    @abstractmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""

    # --- DHW capabilities ---

    @property
    def supports_dhw(self) -> bool:
        """Return True if the heat pump supports Domestic Hot Water.

        Note: This indicates hardware capability, not current configuration.
        Even models without integrated DHW can support external tanks.
        """
        return True

    @property
    def dhw_min_temp(self) -> int | None:
        """Return minimum DHW temperature in °C, or None if not applicable."""
        return 30

    @property
    def dhw_max_temp(self) -> int | None:
        """Return maximum DHW temperature in °C (heat pump only, no electric boost).

        This is the max temperature achievable by the heat pump alone.
        Electric resistance heaters may achieve higher temps.
        """
        return 55

    # --- Circuit capabilities ---

    @property
    def max_circuits(self) -> int:
        """Return maximum number of heating/cooling circuits supported.

        This is the hardware limit. Actual active circuits depend on system_config.
        """
        return 2

    @property
    def supports_circuit1(self) -> bool:
        """Return True if the heat pump supports heating circuit 1."""
        return self.max_circuits >= 1

    @property
    def supports_circuit2(self) -> bool:
        """Return True if the heat pump supports heating circuit 2."""
        return self.max_circuits >= 2

    @property
    def supports_cooling(self) -> bool:
        """Return True if the heat pump can provide cooling.

        Some models require a cooling kit, others have it built-in.
        """
        return True

    @property
    def max_water_outlet_temp(self) -> int:
        """Return maximum water outlet temperature in °C."""
        return 60

    # --- Special features ---

    @property
    def supports_high_temperature(self) -> bool:
        """Return True if this is a high-temperature model (e.g., S80).

        High-temp models can reach 80°C water outlet even at -20°C outdoor.
        """
        return False

    @property
    def supports_secondary_compressor(self) -> bool:
        """Return True if the heat pump has a secondary compressor.

        Only S80 has a cascade R410A + R134a compressor system.
        """
        return False

    @property
    def supports_boiler(self) -> bool:
        """Return True if the heat pump supports a backup boiler."""
        return True

    @property
    def supports_pool(self) -> bool:
        """Return True if the heat pump supports pool heating."""
        return True

    @property
    def extra_register_keys(self) -> list[str]:
        """Return the extra register keys for the profile."""
        return []

    @property
    def entity_overrides(self) -> dict:
        """Return a dictionary of entity overrides for the profile.

        This allows a profile to modify the behavior or parameters of
        specific entities, such as changing temperature limits for a
        water heater or altering the logic for a binary sensor.
        """
        return {}
