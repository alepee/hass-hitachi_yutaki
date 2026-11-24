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

    def test_update_delegation(self, clock):
        """Test that ThermalPowerService delegates to accumulator."""
        acc = ThermalEnergyAccumulator(clock=clock)
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

    def test_update_invalid_data(self, clock):
        """Test update with None values."""
        acc = ThermalEnergyAccumulator(clock=clock)
        service = ThermalPowerService(acc)

        # First successful update to set some state
        service.update(30.0, 35.0, 1.0, 20.0)

        # Update with None values
        service.update(None, 35.0, 1.0, 20.0)
        assert service.get_heating_power() == 0.0

    def test_getters_rounding(self, clock):
        """Test that getters return rounded values."""
        acc = ThermalEnergyAccumulator(clock=clock)
        service = ThermalPowerService(acc)

        # Simulate an accumulation that results in many decimals
        # Force a value in the accumulator
        acc._daily_heating_energy = 1.234567
        assert service.get_daily_heating_energy() == 1.23

    def test_dhw_operation_mode_passed_to_accumulator(self, clock):
        """Test that operation_mode is forwarded to the accumulator."""
        acc = ThermalEnergyAccumulator(clock=clock)
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

    def test_operation_mode_none_preserves_delta_t_logic(self, clock):
        """Test that without operation_mode, ΔT-based classification is used."""
        acc = ThermalEnergyAccumulator(clock=clock)
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


class TestPostCycleInertia:
    """With the compressor stopped, only the inertia of its last output counts."""

    @staticmethod
    def _service(clock):
        clock.seconds = 1000.0
        return ThermalPowerService(ThermalEnergyAccumulator(clock=clock))

    @staticmethod
    def _poll(clock, service, inlet, outlet, frequency):
        clock.seconds += 300.0
        service.update(
            water_inlet_temp=inlet,
            water_outlet_temp=outlet,
            water_flow=1.0,
            compressor_frequency=frequency,
        )

    def test_inverted_delta_t_after_heating_is_not_counted_as_cooling(self, clock):
        """TLA+ trace: heat, stop with flat ΔT, then ΔT turns negative."""
        service = self._service(clock)
        self._poll(clock, service, 30.0, 35.0, 40.0)  # compressor heats
        self._poll(clock, service, 30.0, 35.0, 40.0)
        self._poll(clock, service, 30.0, 30.0, 0.0)  # stops, ΔT flat: lock
        self._poll(clock, service, 31.0, 30.0, 0.0)  # stopped water cools down
        self._poll(clock, service, 31.0, 30.0, 0.0)

        assert service.get_cooling_power() == 0.0
        assert service.get_total_cooling_energy() == 0.0

    def test_delta_t_inside_deadband_ends_heating_inertia(self, clock):
        """A thermistor offset below the deadband is not heat production."""
        service = self._service(clock)
        self._poll(clock, service, 30.0, 35.0, 40.0)
        self._poll(clock, service, 30.0, 35.0, 40.0)
        heating_while_running = service.get_total_heating_energy()
        # Compressor off, outlet keeps reading 0.3 K above inlet for hours.
        self._poll(clock, service, 30.0, 30.3, 0.0)  # closes the running interval
        closed = service.get_total_heating_energy()
        assert closed > heating_while_running
        for _ in range(24):
            self._poll(clock, service, 30.0, 30.3, 0.0)

        assert service.get_heating_power() == 0.0
        assert service.get_total_heating_energy() == closed

    def test_delta_t_inside_deadband_ends_cooling_inertia(self, clock):
        """The cooling side gets the same deadband as the heating side."""
        service = self._service(clock)
        self._poll(clock, service, 20.0, 15.0, 40.0)
        self._poll(clock, service, 20.0, 15.0, 40.0)
        self._poll(clock, service, 20.0, 19.7, 0.0)
        closed = service.get_total_cooling_energy()
        for _ in range(24):
            self._poll(clock, service, 20.0, 19.7, 0.0)

        assert service.get_cooling_power() == 0.0
        assert service.get_total_cooling_energy() == closed

    def test_real_inertia_is_still_counted(self, clock):
        """A clear ΔT in the produced direction keeps counting after a stop."""
        service = self._service(clock)
        self._poll(clock, service, 30.0, 35.0, 40.0)
        self._poll(clock, service, 30.0, 33.0, 0.0)

        assert service.get_heating_power() == pytest.approx(3.49, abs=0.01)

    @pytest.mark.parametrize(("inlet", "outlet"), [(31.0, 30.0), (30.0, 31.0)])
    def test_unknown_production_counts_nothing_while_stopped(
        self, clock, inlet, outlet
    ):
        """After a restart with the compressor off, no output is known yet."""
        service = self._service(clock)
        for _ in range(3):
            self._poll(clock, service, inlet, outlet, 0.0)

        assert service.get_total_heating_energy() == 0.0
        assert service.get_total_cooling_energy() == 0.0

    def test_unreadable_temperatures_while_stopped_lock_until_restart(self, clock):
        """A stop seen through dropped inputs (defrost recovery) still locks."""
        service = self._service(clock)
        self._poll(clock, service, 30.0, 35.0, 40.0)
        self._poll(clock, service, None, None, 0.0)  # guard distrusts the data
        self._poll(clock, service, 31.0, 30.0, 0.0)  # trusted again, ΔT inverted
        self._poll(clock, service, 30.0, 32.0, 0.0)

        assert service.get_cooling_power() == 0.0
        assert service.get_heating_power() == 0.0
        assert service.get_total_cooling_energy() == 0.0
