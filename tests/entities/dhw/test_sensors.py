"""Tests for DHW sensor value functions."""

from unittest.mock import MagicMock

from custom_components.hitachi_yutaki.entities.dhw.sensors import (
    DHW_DEMAND_MODE_HIGH_DEMAND,
    DHW_DEMAND_MODE_STANDARD,
    _dhw_demand_mode_value,
)


class TestDhwDemandModeValue:
    """Test _dhw_demand_mode_value mapping."""

    def _make_coordinator(self, value):
        coordinator = MagicMock()
        coordinator.data = {"dhw_demand_mode": value}
        return coordinator

    def test_standard_mode(self):
        """Register value 0 maps to standard."""
        assert (
            _dhw_demand_mode_value(self._make_coordinator(0))
            == DHW_DEMAND_MODE_STANDARD
        )

    def test_high_demand_mode(self):
        """Register value 1 maps to high_demand."""
        assert (
            _dhw_demand_mode_value(self._make_coordinator(1))
            == DHW_DEMAND_MODE_HIGH_DEMAND
        )

    def test_none_when_missing(self):
        """Missing register returns None."""
        coordinator = MagicMock()
        coordinator.data = {}
        assert _dhw_demand_mode_value(coordinator) is None

    def test_none_when_value_none(self):
        """Explicit None value returns None."""
        assert _dhw_demand_mode_value(self._make_coordinator(None)) is None
