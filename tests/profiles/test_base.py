"""Tests for base profile class and profile registry."""

from custom_components.hitachi_yutaki.profiles import PROFILES
from custom_components.hitachi_yutaki.profiles.base import HitachiHeatPumpProfile
from custom_components.hitachi_yutaki.profiles.yutaki_m import YutakiMProfile
from custom_components.hitachi_yutaki.profiles.yutaki_s import YutakiSProfile
from custom_components.hitachi_yutaki.profiles.yutaki_s80 import YutakiS80Profile
from custom_components.hitachi_yutaki.profiles.yutaki_s_combi import YutakiSCombiProfile
from custom_components.hitachi_yutaki.profiles.yutampo_r32 import YutampoR32Profile


class TestProfileRegistry:
    """Test profile registry (PROFILES dict)."""

    def test_all_profiles_registered(self):
        """Test all profiles are in the registry."""
        assert "yutaki_s" in PROFILES
        assert "yutaki_s_combi" in PROFILES
        assert "yutaki_s80" in PROFILES
        assert "yutaki_m" in PROFILES
        assert "yutampo_r32" in PROFILES

    def test_profile_classes(self):
        """Test profile classes are correct."""
        assert PROFILES["yutaki_s"] is YutakiSProfile
        assert PROFILES["yutaki_s_combi"] is YutakiSCombiProfile
        assert PROFILES["yutaki_s80"] is YutakiS80Profile
        assert PROFILES["yutaki_m"] is YutakiMProfile
        assert PROFILES["yutampo_r32"] is YutampoR32Profile

    def test_all_profiles_inherit_base(self):
        """Test all profiles inherit from base class."""
        for profile_class in PROFILES.values():
            assert issubclass(profile_class, HitachiHeatPumpProfile)
