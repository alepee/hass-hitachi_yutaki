"""Tests for ThermalEnergyAccumulator logic."""

from unittest.mock import patch

import pytest

from custom_components.hitachi_yutaki.domain.services.thermal.accumulator import (
    ThermalEnergyAccumulator,
)


class TestThermalEnergyAccumulator:
    """Tests for ThermalEnergyAccumulator logic."""

    def test_initial_state(self):
        """Test initial values of the accumulator."""
        acc = ThermalEnergyAccumulator(1.0, 10.0, 2.0, 20.0)
        assert acc.daily_heating_energy == 1.0
        assert acc.total_heating_energy == 10.0
        assert acc.daily_cooling_energy == 2.0
        assert acc.total_cooling_energy == 20.0
        assert acc.last_heating_power == 0.0
        assert acc.last_cooling_power == 0.0

    @patch("custom_components.hitachi_yutaki.domain.services.thermal.accumulator.time")
    def test_heating_accumulation(self, mock_time):
        """Test heating energy accumulation."""
        acc = ThermalEnergyAccumulator()

        # Start at T=0
        mock_time.return_value = 1000.0
        acc.update(heating_power=10.0, cooling_power=0.0, compressor_running=True)

        # T=3600 (1 hour later)
        mock_time.return_value = 1000.0 + 3600.0
        acc.update(heating_power=10.0, cooling_power=0.0, compressor_running=True)

        # Energy = avg_power * hours = 10kW * 1h = 10kWh
        assert acc.daily_heating_energy == 10.0
        assert acc.total_heating_energy == 10.0
        assert acc.last_heating_power == 10.0

    @patch("custom_components.hitachi_yutaki.domain.services.thermal.accumulator.time")
    def test_post_cycle_lock(self, mock_time):
        """Test the post-cycle lock logic."""
        acc = ThermalEnergyAccumulator()
        mock_time.return_value = 1000.0

        # 1. Compressor running, heating active
        acc.update(heating_power=10.0, cooling_power=0.0, compressor_running=True)
        assert acc.last_heating_power == 10.0

        # 2. Compressor stops, heating still has inertia (delta T > 0)
        acc.update(heating_power=5.0, cooling_power=0.0, compressor_running=False)
        assert acc.last_heating_power == 5.0
        assert acc._post_cycle_lock is False

        # 3. Delta T drops to 0 while compressor stopped -> lock engaged
        acc.update(heating_power=0.0, cooling_power=0.0, compressor_running=False)
        assert acc._post_cycle_lock is True
        assert acc.last_heating_power == 0.0

        # 4. Delta T goes back up (noise or pump restart) but compressor still stopped -> stay locked
        acc.update(heating_power=2.0, cooling_power=0.0, compressor_running=False)
        assert acc._post_cycle_lock is True
        assert acc.last_heating_power == 0.0  # Power forced to 0

        # 5. Compressor restarts -> lock released
        acc.update(heating_power=2.0, cooling_power=0.0, compressor_running=True)
        assert acc._post_cycle_lock is False
        assert acc.last_heating_power == 2.0

    @patch("custom_components.hitachi_yutaki.domain.services.thermal.accumulator.time")
    def test_post_cycle_lock_cooling(self, mock_time):
        """Test the post-cycle lock logic for cooling mode."""
        acc = ThermalEnergyAccumulator()
        mock_time.return_value = 1000.0

        # 1. Compressor running, cooling active
        acc.update(heating_power=0.0, cooling_power=10.0, compressor_running=True)
        assert acc.last_cooling_power == 10.0
        assert acc._last_mode == "cooling"

        # 2. Compressor stops, cooling still has inertia (delta T < 0)
        acc.update(heating_power=0.0, cooling_power=5.0, compressor_running=False)
        assert acc.last_cooling_power == 5.0
        assert acc._post_cycle_lock is False

        # 3. Delta T drops to 0 while compressor stopped -> lock engaged
        acc.update(heating_power=0.0, cooling_power=0.0, compressor_running=False)
        assert acc._post_cycle_lock is True
        assert acc.last_cooling_power == 0.0

        # 4. Delta T goes back (noise) but compressor still stopped -> stay locked
        acc.update(heating_power=0.0, cooling_power=2.0, compressor_running=False)
        assert acc._post_cycle_lock is True
        assert acc.last_cooling_power == 0.0  # Power forced to 0

        # 5. Compressor restarts -> lock released
        acc.update(heating_power=0.0, cooling_power=2.0, compressor_running=True)
        assert acc._post_cycle_lock is False
        assert acc.last_cooling_power == 2.0

    @patch("custom_components.hitachi_yutaki.domain.services.thermal.accumulator.time")
    def test_defrost_handling(self, mock_time):
        """Test handling of defrost mode."""
        acc = ThermalEnergyAccumulator()
        mock_time.return_value = 1000.0
        acc.update(heating_power=10.0, cooling_power=0.0, compressor_running=True)

        # Defrost starts
        mock_time.return_value = 1000.0 + 600.0  # 10 min
        acc.update(
            heating_power=0.0,
            cooling_power=0.0,
            compressor_running=True,
            is_defrosting=True,
        )

        # Accumulation should have happened for the previous period (0.0 power used during defrost interval)
        # Avg power = (10 + 0) / 2 = 5kW
        # Time = 1/6 h
        # Energy = 5 * 1/6 = 0.833 kWh
        assert acc.daily_heating_energy == pytest.approx(0.833, rel=1e-2)
        assert acc.last_heating_power == 0.0
