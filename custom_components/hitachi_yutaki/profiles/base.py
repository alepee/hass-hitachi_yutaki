"""Domain base class for profile implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable


class HitachiHeatPumpProfile(ABC):
    """Abstract profile describing model-specific capabilities and rules."""

    @property
    @abstractmethod
    def model_key(self) -> str:
        """Canonical model key (protocol-agnostic), for example ``"yutaki_s80"``."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable model name, for example ``"Yutaki S80"``."""

    # Example capability flags. We'll extend as we migrate logic.
    @property
    @abstractmethod
    def supports_dhw(self) -> bool:
        """True if the model supports domestic hot water (DHW)."""
        ...

    @property
    @abstractmethod
    def supports_pool(self) -> bool:
        """True if the model supports pool heating/cooling."""
        ...

    @property
    @abstractmethod
    def supports_circuit1(self) -> bool:
        """True if circuit 1 is supported by the model family.

        Whether heating or cooling is available depends on configuration and
        capabilities, not on the profile.
        """
        ...

    @property
    @abstractmethod
    def supports_circuit2(self) -> bool:
        """True if circuit 2 is supported by the model family.

        Whether heating or cooling is available depends on configuration and
        capabilities, not on the profile.
        """
        ...

    def extra_register_keys(self) -> Iterable[str]:
        """Return extra logical keys to read for this profile.

        Example: S80 models add R134a-specific keys. Default: none.
        """
        return ()

    def entity_overrides(
        self, register_key: str, platform: str, coordinator
    ) -> dict | None:
        """Return platform-specific overrides or None to skip entity creation.

        Default: no special handling (return empty dict). Profiles may override
        to gate creation or provide dynamic UI/feature tweaks per entity.
        """
        return {}
