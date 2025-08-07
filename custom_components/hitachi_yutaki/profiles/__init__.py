"""Profiles (domain layer) for Hitachi Yutaki integration.

Defines the abstract model profile and a simple factory placeholder.
This scaffolding enables moving business logic out of the coordinator incrementally.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Any, Optional


class HitachiHeatPumpProfile(ABC):
    """Abstract profile describing model-specific capabilities and rules."""

    @property
    @abstractmethod
    def model_key(self) -> str:
        """Canonical model key (protocol-agnostic), e.g. "yutaki_s80"."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable model name."""

    # Example capability flags. We'll extend as we migrate logic.
    @property
    @abstractmethod
    def supports_dhw(self) -> bool: ...

    @property
    @abstractmethod
    def supports_pool(self) -> bool: ...

    @property
    @abstractmethod
    def supports_circuit1_heating(self) -> bool: ...

    @property
    @abstractmethod
    def supports_circuit1_cooling(self) -> bool: ...

    @property
    @abstractmethod
    def supports_circuit2_heating(self) -> bool: ...

    @property
    @abstractmethod
    def supports_circuit2_cooling(self) -> bool: ...

    def extra_register_keys(self) -> Iterable[str]:
        """Return extra logical keys to read for this profile.

        Example: S80 models add R134a-specific keys. Default: none.
        """
        return ()


# Simple factory placeholder. Will be expanded to real mappings later.
# Register known profiles here (by canonical model key)
from .yutaki_s80 import YutakiS80Profile
from .yutaki_s import YutakiSProfile
from .yutaki_s_combi import YutakiSCombiProfile
from .yutaki_m import YutakiMProfile
from .yutampo_r32 import YutampoR32Profile

MODEL_KEY_TO_PROFILE: dict[str, type[HitachiHeatPumpProfile]] = {
    "yutaki_s80": YutakiS80Profile,
    "yutaki_s": YutakiSProfile,
    "yutaki_s_combi": YutakiSCombiProfile,
    "yutaki_m": YutakiMProfile,
    "yutampo_r32": YutampoR32Profile,
}


# Temporary helper: translate legacy numeric ids to canonical keys.
# This keeps Modbus details out of profiles while we transition callers to use keys directly.
from ..const import (
    UNIT_MODEL_YUTAKI_S,
    UNIT_MODEL_YUTAKI_S_COMBI,
    UNIT_MODEL_S80,
    UNIT_MODEL_M,
)

_NUMERIC_TO_KEY = {
    UNIT_MODEL_YUTAKI_S: "yutaki_s",
    UNIT_MODEL_YUTAKI_S_COMBI: "yutaki_s_combi",
    UNIT_MODEL_S80: "yutaki_s80",
    UNIT_MODEL_M: "yutaki_m",
}


def model_key_from_numeric(model_numeric: Optional[int]) -> Optional[str]:
    if model_numeric is None:
        return None
    return _NUMERIC_TO_KEY.get(model_numeric)


def get_heat_pump_profile(model_key: Optional[str]) -> HitachiHeatPumpProfile | None:
    if model_key is None:
        return None
    cls = MODEL_KEY_TO_PROFILE.get(model_key)
    return cls() if cls else None
