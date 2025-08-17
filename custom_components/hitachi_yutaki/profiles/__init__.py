"""Profiles (domain layer) for Hitachi Heat Pump integration.

Defines the abstract model profile and a simple factory placeholder.
This scaffolding enables moving business logic out of the coordinator incrementally.
"""

from __future__ import annotations

from .base import HitachiHeatPumpProfile
from .yutaki_m import YutakiMProfile
from .yutaki_s import YutakiSProfile
from .yutaki_s80 import YutakiS80Profile
from .yutaki_s_combi import YutakiSCombiProfile
from .yutampo_r32 import YutampoR32Profile

__all__ = [
    "HitachiHeatPumpProfile",
    "MODEL_KEY_TO_PROFILE",
    "get_heat_pump_profile",
]


# Simple factory placeholder. Will be expanded to real mappings later.
# Register known profiles here (by canonical model key)

MODEL_KEY_TO_PROFILE: dict[str, type[HitachiHeatPumpProfile]] = {
    "yutaki_s80": YutakiS80Profile,
    "yutaki_s": YutakiSProfile,
    "yutaki_s_combi": YutakiSCombiProfile,
    "yutaki_m": YutakiMProfile,
    "yutampo_r32": YutampoR32Profile,
}


def get_heat_pump_profile(model_key: str | None) -> HitachiHeatPumpProfile | None:
    """Instantiate the concrete profile class for a given canonical model key."""
    if model_key is None:
        return None
    cls = MODEL_KEY_TO_PROFILE.get(model_key)
    return cls() if cls else None
