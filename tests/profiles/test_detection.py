"""Tests for profile detection logic."""

import pytest

from custom_components.hitachi_yutaki.profiles import PROFILES
from custom_components.hitachi_yutaki.profiles.yutaki_s_combi import YutakiSCombiProfile
from custom_components.hitachi_yutaki.profiles.yutampo_r32 import YutampoR32Profile


class TestDetectionUniqueness:
    """Test that exactly one profile matches for each valid configuration."""

    @pytest.mark.parametrize(
        ("data", "expected_profile"),
        [
            ({"unit_model": "yutaki_s"}, "yutaki_s"),
            ({"unit_model": "yutaki_s80"}, "yutaki_s80"),
            ({"unit_model": "yutaki_m"}, "yutaki_m"),
            (
                {
                    "unit_model": "yutaki_s_combi",
                    "has_dhw": True,
                    "has_circuit1_heating": True,
                },
                "yutaki_s_combi",
            ),
            (
                {
                    "unit_model": "yutaki_s_combi",
                    "has_dhw": True,
                    "has_circuit1_heating": False,
                    "has_circuit1_cooling": False,
                    "has_circuit2_heating": False,
                    "has_circuit2_cooling": False,
                },
                "yutampo_r32",
            ),
        ],
    )
    def test_exactly_one_profile_matches(self, data, expected_profile):
        """Test that exactly one profile matches for each configuration."""
        matching = [key for key, profile in PROFILES.items() if profile.detect(data)]
        assert len(matching) == 1, f"Expected 1 match, got {matching}"
        assert matching[0] == expected_profile


class TestDetectionWithMissingData:
    """Test detection robustness with missing or None values."""

    def test_missing_unit_model_matches_nothing(self):
        """No profile should match when unit_model is missing."""
        matching = [key for key, profile in PROFILES.items() if profile.detect({})]
        assert len(matching) == 0

    def test_none_unit_model_matches_nothing(self):
        """No profile should match when unit_model is None."""
        data = {"unit_model": None}
        matching = [key for key, profile in PROFILES.items() if profile.detect(data)]
        assert len(matching) == 0

    def test_unknown_unit_model_matches_nothing(self):
        """No profile should match for unknown unit_model."""
        data = {"unit_model": "unknown_model"}
        matching = [key for key, profile in PROFILES.items() if profile.detect(data)]
        assert len(matching) == 0


class TestSCombiVsYutampoDetection:
    """Test the complex detection logic between S Combi and Yutampo R32."""

    def test_s_combi_with_circuit1_heating(self):
        """S Combi detected with circuit1 heating."""
        data = {
            "unit_model": "yutaki_s_combi",
            "has_circuit1_heating": True,
        }
        assert YutakiSCombiProfile.detect(data) is True
        assert YutampoR32Profile.detect(data) is False

    def test_s_combi_with_circuit1_cooling(self):
        """S Combi detected with circuit1 cooling."""
        data = {
            "unit_model": "yutaki_s_combi",
            "has_circuit1_cooling": True,
        }
        assert YutakiSCombiProfile.detect(data) is True

    def test_s_combi_with_circuit2_only(self):
        """S Combi detected even with only circuit2 configured."""
        data = {
            "unit_model": "yutaki_s_combi",
            "has_circuit1_heating": False,
            "has_circuit1_cooling": False,
            "has_circuit2_heating": True,
        }
        assert YutakiSCombiProfile.detect(data) is True
        assert YutampoR32Profile.detect(data) is False

    def test_yutampo_with_dhw_only(self):
        """Yutampo R32 detected with DHW and no circuits."""
        data = {
            "unit_model": "yutaki_s_combi",
            "has_dhw": True,
            "has_circuit1_heating": False,
            "has_circuit1_cooling": False,
            "has_circuit2_heating": False,
            "has_circuit2_cooling": False,
        }
        assert YutampoR32Profile.detect(data) is True
        assert YutakiSCombiProfile.detect(data) is False

    def test_yutampo_requires_dhw(self):
        """Yutampo R32 requires has_dhw to be True."""
        data = {
            "unit_model": "yutaki_s_combi",
            "has_dhw": False,
            "has_circuit1_heating": False,
            "has_circuit1_cooling": False,
            "has_circuit2_heating": False,
            "has_circuit2_cooling": False,
        }
        assert YutampoR32Profile.detect(data) is False
        # S Combi also doesn't match (no circuits)
        assert YutakiSCombiProfile.detect(data) is False


class TestCircuitCapabilitiesCoherence:
    """Test coherence between max_circuits and supports_circuit1/2."""

    @pytest.mark.parametrize("profile_key", PROFILES.keys())
    def test_supports_circuit_derived_from_max_circuits(self, profile_key):
        """Verify supports_circuit1/2 are correctly derived from max_circuits."""
        profile = PROFILES[profile_key]()
        assert profile.supports_circuit1 == (profile.max_circuits >= 1)
        assert profile.supports_circuit2 == (profile.max_circuits >= 2)
