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


class TestCapabilityDefaults:
    """Capability flags that gate entity creation (issue #365)."""

    def test_full_heat_pump_defaults(self):
        """Full heat pumps expose the water circuit and extended compressor."""
        profile = YutakiSProfile()
        assert profile.supports_water_circuit is True
        assert profile.supports_extended_compressor_sensors is True

    def test_yutampo_is_dhw_only(self):
        """Yutampo R32 has no water circuit and a reduced compressor package."""
        profile = YutampoR32Profile()
        assert profile.supports_water_circuit is False
        assert profile.supports_extended_compressor_sensors is False
        # Existing DHW-only expectations still hold.
        assert profile.max_circuits == 0
        assert profile.supports_pool is False
        assert profile.supports_boiler is False


class TestGasSuperheatRange:
    """Per-profile gas-line superheat plausibility range and observed band (#393)."""

    def test_range_is_float_two_tuple_for_every_profile(self):
        """Every profile returns (-10.0, 80.0) as a float 2-tuple with min < max."""
        for profile_class in PROFILES.values():
            rng = profile_class().gas_superheat_plausible_range
            assert isinstance(rng, tuple)
            assert len(rng) == 2
            low, high = rng
            assert isinstance(low, float)
            assert isinstance(high, float)
            assert low < high
            assert rng == (-10.0, 80.0)

    def test_observed_band_is_none_or_valid_two_tuple(self):
        """The observed band is None or a 2-tuple with min <= max."""
        for profile_class in PROFILES.values():
            band = profile_class().gas_superheat_observed_band
            if band is None:
                continue
            assert isinstance(band, tuple)
            assert len(band) == 2
            low, high = band
            assert isinstance(low, float)
            assert isinstance(high, float)
            assert low <= high

    def test_observed_band_spot_checks(self):
        """Calibrated models declare their observed band; Yutaki M declares none."""
        assert YutakiSProfile().gas_superheat_observed_band == (25.0, 51.0)
        assert YutakiSCombiProfile().gas_superheat_observed_band == (39.0, 47.5)
        assert YutakiS80Profile().gas_superheat_observed_band == (45.5, 50.5)
        assert YutakiMProfile().gas_superheat_observed_band is None
