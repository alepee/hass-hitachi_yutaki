"""Tests for entity migration."""


from custom_components.hitachi_yutaki.entity_migration import _calculate_new_unique_id


class TestCalculateNewUniqueId:
    """Test the _calculate_new_unique_id function."""

    def test_simple_migration(self):
        """Test simple migration (slave_id removal only)."""
        # Test various simple migrations
        test_cases = [
            ("abc123_1_outdoor_temp", 1, "abc123_outdoor_temp"),
            ("abc123_1_water_inlet_temp", 1, "abc123_water_inlet_temp"),
            ("abc123_1_water_outlet_temp", 1, "abc123_water_outlet_temp"),
            ("abc123_1_operation_state", 1, "abc123_operation_state"),
            ("abc123_1_connectivity", 1, "abc123_connectivity"),
        ]

        for old_id, slave_id, expected_new_id in test_cases:
            result = _calculate_new_unique_id(old_id, slave_id)
            assert result == expected_new_id, f"Failed for {old_id}"

    def test_complex_migration_with_key_rename(self):
        """Test complex migration (slave_id removal + key rename)."""
        # Test migrations with key renaming
        test_cases = [
            ("abc123_1_alarm_code", 1, "abc123_alarm"),
            ("abc123_1_thermal_power", 1, "abc123_thermal_power_heating"),
            (
                "abc123_1_daily_thermal_energy",
                1,
                "abc123_thermal_energy_heating_daily",
            ),
            (
                "abc123_1_total_thermal_energy",
                1,
                "abc123_thermal_energy_heating_total",
            ),
        ]

        for old_id, slave_id, expected_new_id in test_cases:
            result = _calculate_new_unique_id(old_id, slave_id)
            assert result == expected_new_id, f"Failed for {old_id}"

    def test_migration_with_circuit_prefix(self):
        """Test migration with circuit prefix."""
        # Test circuit entities
        test_cases = [
            ("abc123_1_circuit1_climate", 1, "abc123_circuit1_climate"),
            ("abc123_1_circuit2_climate", 1, "abc123_circuit2_climate"),
            ("abc123_1_circuit1_thermostat", 1, "abc123_circuit1_thermostat"),
            ("abc123_1_circuit2_eco_mode", 1, "abc123_circuit2_eco_mode"),
            (
                "abc123_1_circuit1_max_flow_temp_heating_otc",
                1,
                "abc123_circuit1_max_flow_temp_heating_otc",
            ),
        ]

        for old_id, slave_id, expected_new_id in test_cases:
            result = _calculate_new_unique_id(old_id, slave_id)
            assert result == expected_new_id, f"Failed for {old_id}"

    def test_migration_with_dhw_prefix(self):
        """Test migration with DHW prefix."""
        # Test DHW entities
        test_cases = [
            ("abc123_1_dhw", 1, "abc123_dhw"),
            ("abc123_1_dhw_antilegionella", 1, "abc123_dhw_antilegionella"),
        ]

        for old_id, slave_id, expected_new_id in test_cases:
            result = _calculate_new_unique_id(old_id, slave_id)
            assert result == expected_new_id, f"Failed for {old_id}"

    def test_migration_with_otc_key_rename(self):
        """Test migration with OTC method key rename."""
        # Test OTC method migrations
        test_cases = [
            (
                "abc123_1_circuit1_otc_method_heating",
                1,
                "abc123_circuit1_otc_calculation_method_heating",
            ),
            (
                "abc123_1_circuit2_otc_method_heating",
                1,
                "abc123_circuit2_otc_calculation_method_heating",
            ),
            (
                "abc123_1_circuit1_otc_method_cooling",
                1,
                "abc123_circuit1_otc_calculation_method_cooling",
            ),
        ]

        for old_id, slave_id, expected_new_id in test_cases:
            result = _calculate_new_unique_id(old_id, slave_id)
            assert result == expected_new_id, f"Failed for {old_id}"

    def test_migration_with_different_slave_ids(self):
        """Test migration with different slave IDs."""
        # Test with slave_id = 2, 3, etc.
        test_cases = [
            ("abc123_2_outdoor_temp", 2, "abc123_outdoor_temp"),
            ("abc123_3_water_inlet_temp", 3, "abc123_water_inlet_temp"),
            ("abc123_5_alarm_code", 5, "abc123_alarm"),
        ]

        for old_id, slave_id, expected_new_id in test_cases:
            result = _calculate_new_unique_id(old_id, slave_id)
            assert result == expected_new_id, f"Failed for {old_id}"

    def test_no_migration_needed(self):
        """Test entities that don't need migration."""
        # Test entities without slave_id pattern
        test_cases = [
            ("abc123_outdoor_temp", 1, None),
            ("abc123_new_entity", 1, None),
        ]

        for old_id, slave_id, expected_new_id in test_cases:
            result = _calculate_new_unique_id(old_id, slave_id)
            assert result == expected_new_id, f"Failed for {old_id}"

    def test_invalid_format(self):
        """Test invalid unique_id format."""
        # Test malformed unique_ids
        test_cases = [
            ("invalid_format", 1, None),
            ("abc123_1", 1, None),  # Missing key part
        ]

        for old_id, slave_id, expected_new_id in test_cases:
            result = _calculate_new_unique_id(old_id, slave_id)
            assert result == expected_new_id, f"Failed for {old_id}"
