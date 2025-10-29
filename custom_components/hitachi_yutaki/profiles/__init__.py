"""Profiles for Hitachi heat pumps."""

import logging

from .base import HitachiHeatPumpProfile
from .yutaki_m import YutakiMProfile
from .yutaki_s import YutakiSProfile
from .yutaki_s80 import YutakiS80Profile
from .yutaki_s_combi import YutakiSCombiProfile
from .yutampo_r32 import YutampoR32Profile

_LOGGER = logging.getLogger(__name__)

PROFILES: dict[str, type[HitachiHeatPumpProfile]] = {
    "yutaki_s": YutakiSProfile,
    "yutaki_s_combi": YutakiSCombiProfile,
    "yutaki_s80": YutakiS80Profile,
    "yutaki_m": YutakiMProfile,
    "yutampo_r32": YutampoR32Profile,
}
