"""Tests for telemetry collector."""

from custom_components.hitachi_yutaki.telemetry.collector import TelemetryCollector
from custom_components.hitachi_yutaki.telemetry.models import TelemetryLevel


def _sample_data(**overrides) -> dict:
    """Create a sample coordinator data dict.

    Includes derived metrics keys that the DerivedMetricsAdapter would
    have injected into coordinator.data before the collector runs.
    """
    data = {
        "is_available": True,
        "outdoor_temp": 5.5,
        "water_inlet_temp": 35.0,
        "water_outlet_temp": 40.5,
        "dhw_current_temp": 52.0,
        "compressor_frequency": 65.0,
        "compressor_current": 8.5,
        "power_consumption": 3.2,
        "unit_mode": 1,  # heat
        "operation_state": "operation_state_heat_thermo_on",
        "circuit1_current_temp": 38.0,
        "circuit2_current_temp": None,
        "water_flow": 1.2,
        # Derived metrics (injected by DerivedMetricsAdapter)
        "thermal_power_heating": 5.81,
        "thermal_power_cooling": None,
        "electrical_power": 1.76,
        "cop_heating": 3.30,
        "cop_cooling": None,
        "cop_heating_quality": "optimal",
        "cop_cooling_quality": None,
    }
    data.update(overrides)
    return data


class TestCollectorLevel:
    """Tests for level-based collection behavior."""

    def test_off_does_not_collect(self):
        """Verify OFF level ignores all data."""
        collector = TelemetryCollector(TelemetryLevel.OFF)
        collector.collect(
            _sample_data(), is_compressor_running=True, is_defrosting=False
        )
        assert collector.buffer_size == 0

    def test_full_collects(self):
        """Verify ON level stores data points in the buffer."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(), is_compressor_running=True, is_defrosting=False
        )
        assert collector.buffer_size == 1


class TestCollectorExtraction:
    """Tests for field extraction from coordinator data."""

    def test_extracts_temperatures(self):
        """Verify all temperature fields are extracted from coordinator data."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(), is_compressor_running=True, is_defrosting=False
        )
        point = collector.flush()[0]
        assert point.outdoor_temp == 5.5
        assert point.water_inlet_temp == 35.0
        assert point.water_outlet_temp == 40.5
        assert point.dhw_temp == 52.0
        assert point.circuit1_water_temp == 38.0
        assert point.circuit2_water_temp is None

    def test_extracts_compressor_state(self):
        """Verify compressor on/off, frequency, and current are extracted."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(), is_compressor_running=True, is_defrosting=False
        )
        point = collector.flush()[0]
        assert point.compressor_on is True
        assert point.compressor_frequency == 65.0
        assert point.compressor_current == 8.5

    def test_reads_thermal_power_from_data(self):
        """Thermal power is read from adapter-injected data."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(thermal_power_heating=5.81),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.thermal_power is not None
        assert abs(point.thermal_power - 5.81) < 0.01

    def test_thermal_power_none_when_not_in_data(self):
        """Thermal power is None when adapter did not inject it."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(thermal_power_heating=None, thermal_power_cooling=None),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.thermal_power is None

    def test_reads_cooling_thermal_power(self):
        """Thermal power reads cooling value when heating is None."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(thermal_power_heating=None, thermal_power_cooling=4.2),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.thermal_power is not None
        assert abs(point.thermal_power - 4.2) < 0.01

    def test_maps_unit_mode(self):
        """unit_mode integer is mapped to string."""
        collector = TelemetryCollector(TelemetryLevel.ON)

        collector.collect(
            _sample_data(unit_mode=0), is_compressor_running=False, is_defrosting=False
        )
        assert collector.flush()[0].unit_mode == "cool"

        collector.collect(
            _sample_data(unit_mode=1), is_compressor_running=False, is_defrosting=False
        )
        assert collector.flush()[0].unit_mode == "heat"

        collector.collect(
            _sample_data(unit_mode=2), is_compressor_running=False, is_defrosting=False
        )
        assert collector.flush()[0].unit_mode == "auto"

    def test_maps_unit_mode_none(self):
        """Verify None unit_mode maps to None string."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(unit_mode=None),
            is_compressor_running=False,
            is_defrosting=False,
        )
        assert collector.flush()[0].unit_mode is None

    def test_detects_dhw_active(self):
        """Verify DHW active state is derived from the operation state string."""
        collector = TelemetryCollector(TelemetryLevel.ON)

        collector.collect(
            _sample_data(operation_state="operation_state_dhw_on"),
            is_compressor_running=True,
            is_defrosting=False,
        )
        assert collector.flush()[0].dhw_active is True

        collector.collect(
            _sample_data(operation_state="operation_state_heat_thermo_on"),
            is_compressor_running=True,
            is_defrosting=False,
        )
        assert collector.flush()[0].dhw_active is False

    def test_defrost_passthrough(self):
        """Verify the is_defrosting flag is passed through to the metric point."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(), is_compressor_running=True, is_defrosting=True
        )
        assert collector.flush()[0].is_defrosting is True

    def test_has_timestamp(self):
        """Verify collected points have a UTC-aware timestamp."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(), is_compressor_running=True, is_defrosting=False
        )
        point = collector.flush()[0]
        assert point.time is not None
        assert point.time.tzinfo is not None  # UTC-aware


class TestCollectorBuffer:
    """Tests for buffer behavior."""

    def test_flush_returns_and_clears(self):
        """Verify flush returns all buffered points and empties the buffer."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(), is_compressor_running=True, is_defrosting=False
        )
        collector.collect(
            _sample_data(), is_compressor_running=True, is_defrosting=False
        )
        assert collector.buffer_size == 2

        points = collector.flush()
        assert len(points) == 2
        assert collector.buffer_size == 0

    def test_flush_empty_buffer(self):
        """Verify flushing an empty buffer returns an empty list."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        assert collector.flush() == []

    def test_buffer_overflow_drops_oldest(self):
        """Verify oldest points are dropped when buffer exceeds max size."""
        collector = TelemetryCollector(TelemetryLevel.ON, buffer_max_size=3)
        for i in range(5):
            collector.collect(
                _sample_data(outdoor_temp=float(i)),
                is_compressor_running=True,
                is_defrosting=False,
            )
        assert collector.buffer_size == 3
        points = collector.flush()
        # Should have the 3 most recent points (temps 2, 3, 4)
        assert points[0].outdoor_temp == 2.0
        assert points[1].outdoor_temp == 3.0
        assert points[2].outdoor_temp == 4.0

    def test_skips_unavailable_data(self):
        """Verify data marked as unavailable is not collected."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            {"is_available": False}, is_compressor_running=False, is_defrosting=False
        )
        assert collector.buffer_size == 0

    def test_skips_empty_data(self):
        """Verify an empty data dict is not collected."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect({}, is_compressor_running=False, is_defrosting=False)
        assert collector.buffer_size == 0

    def test_handles_non_numeric_values(self):
        """Non-numeric values in numeric fields should become None."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(outdoor_temp="invalid", compressor_frequency="N/A"),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.outdoor_temp is None
        assert point.compressor_frequency is None


class TestSentinelFiltering:
    """Tests for Modbus sentinel value filtering."""

    def test_filters_sentinel_minus_127(self):
        """Sentinel -127 (no sensor connected) should become None."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(
                water_outlet_2_temp=-127,
                water_outlet_3_temp=-127,
                pool_current_temp=-127,
            ),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.water_outlet_2_temp is None
        assert point.water_outlet_3_temp is None
        assert point.pool_current_temp is None

    def test_filters_sentinel_minus_67(self):
        """Sentinel -67 (DHW not configured) should become None."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(dhw_current_temp=-67),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.dhw_temp is None

    def test_passes_valid_negative_temps(self):
        """Legitimate negative temperatures (e.g. -10 C outdoor) must pass through."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(outdoor_temp=-10, water_inlet_temp=5),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.outdoor_temp == -10
        assert point.water_inlet_temp == 5


class TestCollectorDerivedMetrics:
    """Tests for reading derived metrics from adapter-injected data."""

    def test_reads_electrical_power_from_data(self):
        """Electrical power is read from adapter-injected data."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(electrical_power=1.76),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.electrical_power is not None
        assert abs(point.electrical_power - 1.76) < 0.01

    def test_electrical_power_none_when_not_in_data(self):
        """Electrical power is None when adapter did not inject it."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(electrical_power=None),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.electrical_power is None

    def test_reads_cop_from_data(self):
        """COP is read from adapter-injected data."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(cop_heating=3.30),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.cop_instant is not None
        assert abs(point.cop_instant - 3.30) < 0.01

    def test_cop_none_when_not_in_data(self):
        """COP is None when adapter did not inject it."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(cop_heating=None, cop_cooling=None),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.cop_instant is None

    def test_reads_cop_quality_from_data(self):
        """COP quality is read from adapter-injected data."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(cop_heating_quality="optimal"),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.cop_quality == "optimal"

    def test_cop_quality_none_when_not_in_data(self):
        """COP quality is None when adapter did not inject it."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(cop_heating_quality=None, cop_cooling_quality=None),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.cop_quality is None

    def test_reads_cooling_cop_when_heating_none(self):
        """COP reads cooling value when heating is None."""
        collector = TelemetryCollector(TelemetryLevel.ON)
        collector.collect(
            _sample_data(cop_heating=None, cop_cooling=2.5),
            is_compressor_running=True,
            is_defrosting=False,
        )
        point = collector.flush()[0]
        assert point.cop_instant is not None
        assert abs(point.cop_instant - 2.5) < 0.01
