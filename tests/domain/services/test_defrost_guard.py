"""Tests for DefrostGuard domain service."""

from unittest.mock import patch

from custom_components.hitachi_yutaki.domain.services.defrost_guard import (
    DefrostGuard,
    DefrostState,
)


class TestDefrostGuard:
    """Tests for DefrostGuard state machine."""

    def test_initial_state_is_normal(self):
        """Test that initial state is NORMAL and data is reliable."""
        guard = DefrostGuard()
        assert guard.state == DefrostState.NORMAL
        assert guard.is_data_reliable is True

    def test_normal_to_defrost(self):
        """Test NORMAL → DEFROST when is_defrosting becomes True."""
        guard = DefrostGuard()
        guard.update(is_defrosting=True, delta_t=5.0)
        assert guard.state == DefrostState.DEFROST
        assert guard.is_data_reliable is False

    def test_defrost_to_recovery(self):
        """Test DEFROST → RECOVERY when is_defrosting becomes False."""
        guard = DefrostGuard()
        guard.update(is_defrosting=True, delta_t=5.0)
        guard.update(is_defrosting=False, delta_t=-2.0)
        assert guard.state == DefrostState.RECOVERY
        assert guard.is_data_reliable is False

    def test_recovery_to_normal_after_stable_readings(self):
        """Test RECOVERY → NORMAL after N stable readings with consistent ΔT sign."""
        guard = DefrostGuard(stable_readings_required=3)

        # Enter defrost during heating (positive ΔT)
        guard.update(is_defrosting=True, delta_t=5.0)
        # Exit defrost
        guard.update(is_defrosting=False, delta_t=-2.0)
        assert guard.state == DefrostState.RECOVERY

        # 3 consecutive readings with positive ΔT (> 0.5 threshold)
        guard.update(is_defrosting=False, delta_t=1.0)
        assert guard.state == DefrostState.RECOVERY
        guard.update(is_defrosting=False, delta_t=2.0)
        assert guard.state == DefrostState.RECOVERY
        guard.update(is_defrosting=False, delta_t=3.0)
        assert guard.state == DefrostState.NORMAL
        assert guard.is_data_reliable is True

    @patch("custom_components.hitachi_yutaki.domain.services.defrost_guard.time")
    def test_recovery_to_normal_on_timeout(self, mock_time):
        """Test RECOVERY → NORMAL when safety timeout elapses."""
        guard = DefrostGuard(stable_readings_required=3, recovery_timeout=300.0)

        mock_time.return_value = 1000.0
        guard.update(is_defrosting=True, delta_t=5.0)

        # Enter recovery
        mock_time.return_value = 1100.0
        guard.update(is_defrosting=False, delta_t=-2.0)
        assert guard.state == DefrostState.RECOVERY

        # Time passes beyond timeout (300s)
        mock_time.return_value = 1100.0 + 300.0
        guard.update(is_defrosting=False, delta_t=-1.0)
        assert guard.state == DefrostState.NORMAL
        assert guard.is_data_reliable is True

    def test_recovery_to_defrost_if_defrost_restarts(self):
        """Test RECOVERY → DEFROST if defrost restarts during recovery."""
        guard = DefrostGuard()

        guard.update(is_defrosting=True, delta_t=5.0)
        guard.update(is_defrosting=False, delta_t=-2.0)
        assert guard.state == DefrostState.RECOVERY

        guard.update(is_defrosting=True, delta_t=-3.0)
        assert guard.state == DefrostState.DEFROST
        assert guard.is_data_reliable is False

    def test_counter_resets_when_delta_t_sign_flips(self):
        """Test that stable counter resets when ΔT sign flips during recovery."""
        guard = DefrostGuard(stable_readings_required=3)

        # Enter defrost during heating
        guard.update(is_defrosting=True, delta_t=5.0)
        guard.update(is_defrosting=False, delta_t=-2.0)

        # 2 stable readings
        guard.update(is_defrosting=False, delta_t=1.0)
        guard.update(is_defrosting=False, delta_t=2.0)
        assert guard.state == DefrostState.RECOVERY

        # ΔT flips — counter resets
        guard.update(is_defrosting=False, delta_t=-1.0)
        assert guard.state == DefrostState.RECOVERY

        # Need 3 more stable readings now
        guard.update(is_defrosting=False, delta_t=1.0)
        guard.update(is_defrosting=False, delta_t=2.0)
        assert guard.state == DefrostState.RECOVERY
        guard.update(is_defrosting=False, delta_t=3.0)
        assert guard.state == DefrostState.NORMAL

    def test_counter_resets_when_delta_t_is_none(self):
        """Test that stable counter resets when ΔT is None during recovery."""
        guard = DefrostGuard(stable_readings_required=3)

        guard.update(is_defrosting=True, delta_t=5.0)
        guard.update(is_defrosting=False, delta_t=-2.0)

        # 2 stable readings
        guard.update(is_defrosting=False, delta_t=1.0)
        guard.update(is_defrosting=False, delta_t=2.0)

        # None ΔT — counter resets
        guard.update(is_defrosting=False, delta_t=None)
        assert guard.state == DefrostState.RECOVERY

        # Need 3 more stable readings
        guard.update(is_defrosting=False, delta_t=1.0)
        guard.update(is_defrosting=False, delta_t=2.0)
        guard.update(is_defrosting=False, delta_t=3.0)
        assert guard.state == DefrostState.NORMAL

    def test_is_data_reliable_false_during_defrost_and_recovery(self):
        """Test is_data_reliable returns False during DEFROST and RECOVERY."""
        guard = DefrostGuard()

        assert guard.is_data_reliable is True

        guard.update(is_defrosting=True, delta_t=5.0)
        assert guard.is_data_reliable is False

        guard.update(is_defrosting=False, delta_t=-2.0)
        assert guard.is_data_reliable is False

    def test_cooling_mode_recovery(self):
        """Test recovery works correctly for cooling mode (negative ΔT)."""
        guard = DefrostGuard(stable_readings_required=2)

        # Enter defrost during cooling (negative ΔT)
        guard.update(is_defrosting=True, delta_t=-3.0)
        guard.update(is_defrosting=False, delta_t=2.0)
        assert guard.state == DefrostState.RECOVERY

        # Need negative ΔT (< -0.5) to stabilize
        guard.update(is_defrosting=False, delta_t=-1.0)
        assert guard.state == DefrostState.RECOVERY
        guard.update(is_defrosting=False, delta_t=-2.0)
        assert guard.state == DefrostState.NORMAL

    def test_delta_t_within_threshold_does_not_count(self):
        """Test that ΔT within ±0.5 threshold doesn't count as stable."""
        guard = DefrostGuard(stable_readings_required=2)

        # Enter defrost during heating
        guard.update(is_defrosting=True, delta_t=5.0)
        guard.update(is_defrosting=False, delta_t=-2.0)

        # ΔT = 0.3 is within threshold, should not count
        guard.update(is_defrosting=False, delta_t=0.3)
        guard.update(is_defrosting=False, delta_t=0.4)
        assert guard.state == DefrostState.RECOVERY

        # ΔT > 0.5 should count
        guard.update(is_defrosting=False, delta_t=1.0)
        guard.update(is_defrosting=False, delta_t=2.0)
        assert guard.state == DefrostState.NORMAL

    def test_no_pre_defrost_sign_uses_timeout(self):
        """Test that when no pre-defrost ΔT sign is available, recovery uses timeout."""
        guard = DefrostGuard(stable_readings_required=2, recovery_timeout=300.0)

        # Enter defrost without a prior ΔT reading
        guard.update(is_defrosting=True, delta_t=None)
        guard.update(is_defrosting=False, delta_t=1.0)
        assert guard.state == DefrostState.RECOVERY

        # Can't stabilize without pre-defrost sign
        guard.update(is_defrosting=False, delta_t=1.0)
        guard.update(is_defrosting=False, delta_t=2.0)
        assert guard.state == DefrostState.RECOVERY

    def test_stays_normal_when_not_defrosting(self):
        """Test that NORMAL state persists when not defrosting."""
        guard = DefrostGuard()
        guard.update(is_defrosting=False, delta_t=5.0)
        assert guard.state == DefrostState.NORMAL
        guard.update(is_defrosting=False, delta_t=-3.0)
        assert guard.state == DefrostState.NORMAL

    def test_stays_in_defrost_while_defrosting(self):
        """Test that DEFROST state persists while defrosting continues."""
        guard = DefrostGuard()
        guard.update(is_defrosting=True, delta_t=5.0)
        assert guard.state == DefrostState.DEFROST
        guard.update(is_defrosting=True, delta_t=-3.0)
        assert guard.state == DefrostState.DEFROST
        guard.update(is_defrosting=True, delta_t=0.0)
        assert guard.state == DefrostState.DEFROST
