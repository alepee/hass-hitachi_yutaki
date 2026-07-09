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
            # dhw_power reads from STATUS (1065) since #295; writes go to CONTROL 1016
            "dhw_power": 1065,
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

    def test_no_duplicate_read_addresses(self):
        """No two distinct semantic keys may share the same read address.

        Pre-2016 (PMML0419A Section 5.2) defines a handful of intentional
        STATUS/CONTROL aliases (one read register surfaced under two keys).
        Those are whitelisted below. Any *other* address collision indicates
        a copy-paste error mapping one key onto an unrelated register --
        which is exactly the bug behind #318 (circuit2_thermostat duplicated
        circuit1_thermostat at address 1029).
        """
        reg_map = AtwMbs02Pre2016RegisterMap()

        # Documented intentional aliases: each pair is the same physical
        # register exposed under two keys (a derived/deserialized view plus
        # the raw value). These legitimately share an address.
        allowed_alias_pairs = {
            frozenset({"operation_state", "operation_state_code"}),
            frozenset({"dhw_antilegionella", "dhw_antilegionella_status"}),
            frozenset(
                {"dhw_antilegionella_temp", "dhw_antilegionella_temp_status"}
            ),
        }

        by_address: dict[int, list[str]] = {}
        for key, definition in reg_map.all_registers.items():
            by_address.setdefault(definition.address, []).append(key)

        for address, keys in by_address.items():
            if len(keys) == 1:
                continue
            assert frozenset(keys) in allowed_alias_pairs, (
                f"Address {address} is shared by {sorted(keys)}, which is not "
                f"a documented STATUS/CONTROL alias pair. See #318."
            )

    def test_single_global_thermostat_register(self):
        """Pre-2016 has ONE shared 'Room Thermostat available' register.

        Unlike the 2016 line-up (which splits the flag into per-circuit
        registers 1010/1021), pre-2016 hardware (PMML0419A Section 5.2)
        exposes a single global flag at address 1029. The integration must
        therefore model it once -- circuit2_thermostat must not exist (it
        would silently shadow circuit1_thermostat). See #318.
        """
        reg_map = AtwMbs02Pre2016RegisterMap()
        regs = reg_map.all_registers
        assert "circuit1_thermostat" in regs
        assert "circuit2_thermostat" not in regs
        assert "circuit1_thermostat" in reg_map.writable_keys
        assert "circuit2_thermostat" not in reg_map.writable_keys

    def test_thermostat_address_correct(self):
        """The shared thermostat flag sits at address 1029.

        Doc anchor: 1028 = DHW Mode, 1029 = Room Thermostat available
        (docs/gateway/atw-mbs-02.md, pre-2016 Control section).
        """
        reg_map = AtwMbs02Pre2016RegisterMap()
        assert reg_map.all_registers["circuit1_thermostat"].address == 1029


    def test_eco_mode_register(self):
        """eco_mode register is present at addr 1027, writable (write_address=1027)."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        regs = reg_map.all_registers
        assert "eco_mode" in regs, "eco_mode missing from all_registers"
        assert regs["eco_mode"].address == 1027
        assert regs["eco_mode"].write_address == 1027
        assert "eco_mode" in reg_map.writable_keys

    def test_eco_offset_register(self):
        """eco_offset register is present at addr 1090, write_address=1030."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        regs = reg_map.all_registers
        assert "eco_offset" in regs, "eco_offset missing from all_registers"
        assert regs["eco_offset"].address == 1090
        assert regs["eco_offset"].write_address == 1030

    def test_eco_offset_not_writable(self):
        """eco_offset is NOT in writable_keys (entity is read-only)."""
        reg_map = AtwMbs02Pre2016RegisterMap()
        assert "eco_offset" not in reg_map.writable_keys

    def test_eco_offset_absent_from_2016_map(self):
        """eco_offset must not appear in the 2016+ register map."""
        from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
            AtwMbs02RegisterMap,
        )
        assert "eco_offset" not in AtwMbs02RegisterMap().all_registers


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
