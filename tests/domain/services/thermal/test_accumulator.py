"""Tests for ThermalEnergyAccumulator logic."""

from unittest.mock import patch

import pytest

from custom_components.hitachi_yutaki.domain.models.operation import (
    MODE_COOLING,
    MODE_DHW,
    MODE_HEATING,
    MODE_POOL,
)
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
        assert acc._last_mode == MODE_COOLING

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
    def test_zero_power_during_defrost(self, mock_time):
        """Test that passing zero powers (as entity layer does during defrost) zeros energy."""
        acc = ThermalEnergyAccumulator()
        mock_time.return_value = 1000.0
        acc.update(heating_power=10.0, cooling_power=0.0, compressor_running=True)

        # Defrost: entity layer passes zero powers
        mock_time.return_value = 1000.0 + 600.0  # 10 min
        acc.update(
            heating_power=0.0,
            cooling_power=0.0,
            compressor_running=True,
        )

        # Accumulation should have happened for the previous period (0.0 power used during defrost interval)
        # Avg power = (10 + 0) / 2 = 5kW
        # Time = 1/6 h
        # Energy = 5 * 1/6 = 0.833 kWh
        assert acc.daily_heating_energy == pytest.approx(0.833, rel=1e-2)
        assert acc.last_heating_power == 0.0

    @patch("custom_components.hitachi_yutaki.domain.services.thermal.accumulator.time")
    def test_dhw_mode_forces_heating_classification(self, mock_time):
        """Test that DHW operation_mode forces energy to heating even with negative ΔT."""
        acc = ThermalEnergyAccumulator()

        # 1. Unit was cooling circuits → accumulator in "cooling" mode
        mock_time.return_value = 1000.0
        acc.update(heating_power=0.0, cooling_power=8.0, compressor_running=True)
        assert acc._last_mode == MODE_COOLING
        assert acc.last_cooling_power == 8.0

        # 2. DHW starts — even if cooling_power > 0 (transient circuit temps),
        #    operation_mode=MODE_DHW should reclassify as heating
        mock_time.return_value = 1000.0 + 3600.0
        acc.update(
            heating_power=0.0,
            cooling_power=6.0,
            compressor_running=True,
            operation_mode=MODE_DHW,
        )

        # Energy should go to heating, not cooling
        assert acc._last_mode == MODE_HEATING
        assert acc.last_heating_power == 6.0
        assert acc.last_cooling_power == 0.0
        # Only 1h of cooling at avg (8+0)/2 = no — let's check actual values
        # First interval: cooling 8kW for 0s (first measurement) → 0 energy
        # Second interval: 1h, but DHW forced heating with 6kW
        # Heating energy = avg(0, 6) * 1h = 3.0 kWh (first heating sample, last was 0)
        assert acc.daily_heating_energy == pytest.approx(3.0, rel=1e-2)

    @patch("custom_components.hitachi_yutaki.domain.services.thermal.accumulator.time")
    def test_pool_mode_forces_heating_classification(self, mock_time):
        """Test that pool operation_mode forces energy to heating."""
        acc = ThermalEnergyAccumulator()

        mock_time.return_value = 1000.0
        acc.update(heating_power=0.0, cooling_power=5.0, compressor_running=True)
        assert acc._last_mode == MODE_COOLING

        mock_time.return_value = 1000.0 + 3600.0
        acc.update(
            heating_power=0.0,
            cooling_power=4.0,
            compressor_running=True,
            operation_mode=MODE_POOL,
        )

        assert acc._last_mode == MODE_HEATING
        assert acc.last_heating_power == 4.0
        assert acc.last_cooling_power == 0.0

    @patch("custom_components.hitachi_yutaki.domain.services.thermal.accumulator.time")
    def test_dhw_mode_with_positive_delta_t(self, mock_time):
        """Test that DHW with positive ΔT (normal case) still works correctly."""
        acc = ThermalEnergyAccumulator()

        mock_time.return_value = 1000.0
        acc.update(
            heating_power=10.0,
            cooling_power=0.0,
            compressor_running=True,
            operation_mode=MODE_DHW,
        )

        assert acc._last_mode == MODE_HEATING
        assert acc.last_heating_power == 10.0
        assert acc.last_cooling_power == 0.0

    def test_none_operation_mode_preserves_existing_behavior(self):
        """Test that omitting operation_mode keeps the ΔT-based classification."""
        acc = ThermalEnergyAccumulator()

        # Without operation_mode, cooling_power > 0 → classified as cooling
        acc.update(heating_power=0.0, cooling_power=5.0, compressor_running=True)
        assert acc._last_mode == MODE_COOLING
        assert acc.last_cooling_power == 5.0
