"""Tests for ThermalPowerService integration."""

import pytest

from custom_components.hitachi_yutaki.domain.models.operation import MODE_DHW
from custom_components.hitachi_yutaki.domain.services.thermal.accumulator import (
    ThermalEnergyAccumulator,
)
from custom_components.hitachi_yutaki.domain.services.thermal.service import (
    ThermalPowerService,
)


class TestThermalPowerService:
    """Tests for ThermalPowerService integration."""

    def test_update_delegation(self):
        """Test that ThermalPowerService delegates to accumulator."""
        acc = ThermalEnergyAccumulator()
        service = ThermalPowerService(acc)

        # Test basic update delegation
        # heating: outlet (35) > inlet (30)
        service.update(
            water_inlet_temp=30.0,
            water_outlet_temp=35.0,
            water_flow=1.0,
            compressor_frequency=20.0,
        )

        # Expected heating power is ~5.81 kW
        assert service.get_heating_power() == pytest.approx(5.81, abs=0.01)
        assert service.get_cooling_power() == 0.0

    def test_update_invalid_data(self):
        """Test update with None values."""
        acc = ThermalEnergyAccumulator()
        service = ThermalPowerService(acc)

        # First successful update to set some state
        service.update(30.0, 35.0, 1.0, 20.0)

        # Update with None values
        service.update(None, 35.0, 1.0, 20.0)
        assert service.get_heating_power() == 0.0

    def test_getters_rounding(self):
        """Test that getters return rounded values."""
        acc = ThermalEnergyAccumulator()
        service = ThermalPowerService(acc)

        # Simulate an accumulation that results in many decimals
        # Force a value in the accumulator
        acc._daily_heating_energy = 1.234567
        assert service.get_daily_heating_energy() == 1.23

    def test_dhw_operation_mode_passed_to_accumulator(self):
        """Test that operation_mode is forwarded to the accumulator."""
        acc = ThermalEnergyAccumulator()
        service = ThermalPowerService(acc)

        # Cooling ΔT (outlet < inlet) but operation_mode=MODE_DHW → should be heating
        service.update(
            water_inlet_temp=35.0,
            water_outlet_temp=30.0,
            water_flow=1.0,
            compressor_frequency=20.0,
            operation_mode=MODE_DHW,
        )

        # DHW forces heating classification even with negative ΔT
        assert service.get_heating_power() == pytest.approx(5.81, abs=0.01)
        assert service.get_cooling_power() == 0.0

    def test_operation_mode_none_preserves_delta_t_logic(self):
        """Test that without operation_mode, ΔT-based classification is used."""
        acc = ThermalEnergyAccumulator()
        service = ThermalPowerService(acc)

        # Cooling ΔT without operation_mode → cooling
        service.update(
            water_inlet_temp=35.0,
            water_outlet_temp=30.0,
            water_flow=1.0,
            compressor_frequency=20.0,
        )

        assert service.get_heating_power() == 0.0
        assert service.get_cooling_power() == pytest.approx(5.81, abs=0.01)
