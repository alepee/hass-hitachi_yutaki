"""Tests for the ATW-MBS-02 (Before Line-up 2016) register map."""

from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02_pre2016 import (
    AtwMbs02Pre2016RegisterMap,
    deserialize_unit_model_pre2016,
)


class TestPre2016RegisterMap:
    """Test the Before Line-up 2016 register map structure."""

    def test_instantiation(self):
        """Can create the map."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        assert reg_map is not None

    def test_all_registers_populated(self):
        """Key registers exist in the map."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        regs = reg_map.all_registers
        for key in [
            "unit_power",
            "outdoor_temp",
            "dhw_current_temp",
            "compressor_frequency",
            "unit_model",
        ]:
            assert key in regs, f"{key} missing from all_registers"

    def test_no_auto_mode(self):
        """Before-2016 units do not support Auto HVAC mode."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        assert reg_map.hvac_unit_mode_auto is None
        assert reg_map.hvac_unit_mode_cool == 0
        assert reg_map.hvac_unit_mode_heat == 1

    def test_writable_keys_populated(self):
        """Writable keys include control registers but exclude eco/boost."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        writable = reg_map.writable_keys
        # Control registers present
        assert "unit_power" in writable
        assert "unit_mode" in writable
        assert "circuit1_power" in writable
        assert "dhw_power" in writable
        assert "dhw_target_temp" in writable
        assert "pool_power" in writable
        # Eco/boost registers absent (don't exist in before-2016)
        assert "circuit1_eco_mode" not in writable
        assert "circuit1_heat_eco_offset" not in writable
        assert "dhw_boost" not in writable
        assert "dhw_high_demand" not in writable

    def test_key_addresses_differ_from_2016(self):
        """Verify key registers are at before-2016 addresses (not 2016 addresses)."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        regs = reg_map.all_registers

        expected_addresses = {
            "operation_state": 1077,
            "outdoor_temp": 1078,
            "water_inlet_temp": 1079,
            "unit_model": 1217,
            "dhw_power": 1016,
            "dhw_current_temp": 1075,
            "system_config": 1074,
        }
        for key, expected_addr in expected_addresses.items():
            assert regs[key].address == expected_addr, (
                f"{key} address is {regs[key].address}, expected {expected_addr}"
            )

    def test_no_eco_mode_keys(self):
        """Before-2016 has no eco mode registers."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        regs = reg_map.all_registers
        for key in [
            "circuit1_eco_mode",
            "circuit1_heat_eco_offset",
            "circuit1_cool_eco_offset",
        ]:
            assert key not in regs, f"{key} should not exist in before-2016 map"

    def test_no_dhw_boost_keys(self):
        """Before-2016 has no DHW boost/high demand registers."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        regs = reg_map.all_registers
        for key in ["dhw_boost", "dhw_high_demand"]:
            assert key not in regs, f"{key} should not exist in before-2016 map"


class TestPre2016UnitModelDeserializer:
    """Test the before-2016 unit model deserializer."""

    def test_known_models(self):
        """Known model IDs map to expected keys."""
        assert deserialize_unit_model_pre2016(0) == "yutaki_s"
        assert deserialize_unit_model_pre2016(1) == "yutaki_s_combi"

    def test_unknown_model(self):
        """Unknown model IDs return 'unknown'."""
        assert deserialize_unit_model_pre2016(2) == "unknown"
        assert deserialize_unit_model_pre2016(99) == "unknown"

    def test_none(self):
        """None input returns 'unknown'."""
        assert deserialize_unit_model_pre2016(None) == "unknown"
