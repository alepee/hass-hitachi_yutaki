"""Cross-gateway compatibility tests between ATW-MBS-02, ATW-MBS-02 Pre-2016, and HC-A(16/64)MB."""

from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02_pre2016 import (
    AtwMbs02Pre2016RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.hc_a_mb import (
    HcAMbRegisterMap,
)


class TestKeyNamingCompatibility:
    """Test that all gateways use the same key names for shared registers."""

    def test_shared_gateway_keys(self):
        """Essential gateway keys should exist in all maps."""
        atw = AtwMbs02RegisterMap()
        pre = AtwMbs02Pre2016RegisterMap()
        hca = HcAMbRegisterMap()

        # These keys must be present in all three
        shared_keys = [
            "alarm_code",
            "unit_model",
            "system_config",
            "system_status",
            "system_state",
        ]
        for key in shared_keys:
            assert key in atw.all_registers, f"{key} missing from ATW-MBS-02"
            assert key in pre.all_registers, f"{key} missing from ATW-MBS-02 Pre-2016"
            assert key in hca.all_registers, f"{key} missing from HC-A(16/64)MB"

    def test_shared_control_unit_keys(self):
        """Essential control unit keys should exist in all maps."""
        atw = AtwMbs02RegisterMap()
        pre = AtwMbs02Pre2016RegisterMap()
        hca = HcAMbRegisterMap()

        shared_keys = [
            "unit_power",
            "unit_mode",
            "operation_state",
            "outdoor_temp",
            "water_inlet_temp",
            "water_outlet_temp",
            "water_flow",
            "pump_speed",
            "power_consumption",
        ]
        for key in shared_keys:
            assert key in atw.all_registers, f"{key} missing from ATW-MBS-02"
            assert key in pre.all_registers, f"{key} missing from ATW-MBS-02 Pre-2016"
            assert key in hca.all_registers, f"{key} missing from HC-A(16/64)MB"

    def test_shared_circuit_keys(self):
        """Essential circuit keys (present in all maps) should exist."""
        atw = AtwMbs02RegisterMap()
        pre = AtwMbs02Pre2016RegisterMap()
        hca = HcAMbRegisterMap()

        for circuit in [1, 2]:
            # These keys exist in all three maps (eco_mode excluded — missing in pre-2016)
            shared_keys = [
                f"circuit{circuit}_power",
                f"circuit{circuit}_otc_calculation_method_heating",
                f"circuit{circuit}_otc_calculation_method_cooling",
                f"circuit{circuit}_target_temp",
                f"circuit{circuit}_current_temp",
            ]
            for key in shared_keys:
                assert key in atw.all_registers, f"{key} missing from ATW-MBS-02"
                assert key in pre.all_registers, (
                    f"{key} missing from ATW-MBS-02 Pre-2016"
                )
                assert key in hca.all_registers, f"{key} missing from HC-A(16/64)MB"

    def test_shared_dhw_keys(self):
        """Essential DHW keys (present in all maps) should exist."""
        atw = AtwMbs02RegisterMap()
        pre = AtwMbs02Pre2016RegisterMap()
        hca = HcAMbRegisterMap()

        # dhw_boost and dhw_high_demand are NOT in pre-2016
        shared_keys = [
            "dhw_power",
            "dhw_target_temp",
            "dhw_current_temp",
        ]
        for key in shared_keys:
            assert key in atw.all_registers, f"{key} missing from ATW-MBS-02"
            assert key in pre.all_registers, f"{key} missing from ATW-MBS-02 Pre-2016"
            assert key in hca.all_registers, f"{key} missing from HC-A(16/64)MB"

    def test_shared_pool_keys(self):
        """Essential pool keys should exist in all maps."""
        atw = AtwMbs02RegisterMap()
        pre = AtwMbs02Pre2016RegisterMap()
        hca = HcAMbRegisterMap()

        shared_keys = ["pool_power", "pool_target_temp", "pool_current_temp"]
        for key in shared_keys:
            assert key in atw.all_registers, f"{key} missing from ATW-MBS-02"
            assert key in pre.all_registers, f"{key} missing from ATW-MBS-02 Pre-2016"
            assert key in hca.all_registers, f"{key} missing from HC-A(16/64)MB"

    def test_shared_primary_compressor_keys(self):
        """All 8 primary compressor keys should exist in all maps."""
        atw = AtwMbs02RegisterMap()
        pre = AtwMbs02Pre2016RegisterMap()
        hca = HcAMbRegisterMap()

        shared_keys = [
            "compressor_tg_gas_temp",
            "compressor_ti_liquid_temp",
            "compressor_td_discharge_temp",
            "compressor_te_evaporator_temp",
            "compressor_evi_indoor_expansion_valve_opening",
            "compressor_evo_outdoor_expansion_valve_opening",
            "compressor_frequency",
            "compressor_current",
        ]
        for key in shared_keys:
            assert key in atw.all_registers, f"{key} missing from ATW-MBS-02"
            assert key in pre.all_registers, f"{key} missing from ATW-MBS-02 Pre-2016"
            assert key in hca.all_registers, f"{key} missing from HC-A(16/64)MB"

    def test_writable_keys_subset(self):
        """HC-A(16/64)MB writable keys should be a subset of all_registers keys."""
        hca = HcAMbRegisterMap()
        for key in hca.writable_keys:
            assert key in hca.all_registers, f"Writable key {key} not in all_registers"


class TestBitMasks:
    """Test bit mask values across gateways."""

    def test_circuit_masks_identical(self):
        """Circuit bit masks should match across all gateways."""
        atw = AtwMbs02RegisterMap()
        pre = AtwMbs02Pre2016RegisterMap()
        hca = HcAMbRegisterMap()
        assert atw.masks_circuit == hca.masks_circuit
        assert atw.masks_circuit == pre.masks_circuit

    def test_status_masks_identical_base(self):
        """Base status masks (bits 0-9) should match across all gateways."""
        atw = AtwMbs02RegisterMap()
        pre = AtwMbs02Pre2016RegisterMap()
        hca = HcAMbRegisterMap()
        assert atw.mask_defrost == hca.mask_defrost == pre.mask_defrost
        assert atw.mask_solar == hca.mask_solar == pre.mask_solar
        assert atw.mask_pump1 == hca.mask_pump1 == pre.mask_pump1
        assert atw.mask_compressor == hca.mask_compressor == pre.mask_compressor
        assert atw.mask_boiler == hca.mask_boiler == pre.mask_boiler
        assert atw.mask_dhw_heater == hca.mask_dhw_heater == pre.mask_dhw_heater
        assert (
            atw.mask_smart_function
            == hca.mask_smart_function
            == pre.mask_smart_function
        )

    def test_hvac_mode_auto_not_supported_for_write(self):
        """HC-A(16/64)MB and Pre-2016 should return None for auto mode."""
        hca = HcAMbRegisterMap()
        pre = AtwMbs02Pre2016RegisterMap()
        assert hca.hvac_unit_mode_auto is None
        assert hca.hvac_unit_mode_cool == 0
        assert hca.hvac_unit_mode_heat == 1
        assert pre.hvac_unit_mode_auto is None
        assert pre.hvac_unit_mode_cool == 0
        assert pre.hvac_unit_mode_heat == 1


class TestPre2016Specifics:
    """Test keys specific to or missing from the Before Line-up 2016 map."""

    def test_lacks_eco_mode_keys(self):
        """Pre-2016 should not have eco mode keys."""
        pre = AtwMbs02Pre2016RegisterMap()
        regs = pre.all_registers
        for key in [
            "circuit1_eco_mode",
            "circuit2_eco_mode",
        ]:
            assert key not in regs, f"{key} should not exist in before-2016 map"

    def test_lacks_dhw_boost_high_demand(self):
        """Pre-2016 should not have DHW boost/high demand keys."""
        pre = AtwMbs02Pre2016RegisterMap()
        regs = pre.all_registers
        for key in ["dhw_boost", "dhw_high_demand"]:
            assert key not in regs, f"{key} should not exist in before-2016 map"

    def test_has_circuit_base_keys(self):
        """Pre-2016 should still have the base circuit keys."""
        pre = AtwMbs02Pre2016RegisterMap()
        regs = pre.all_registers
        for circuit in [1, 2]:
            for suffix in [
                "power",
                "otc_calculation_method_heating",
                "otc_calculation_method_cooling",
                "target_temp",
                "current_temp",
            ]:
                key = f"circuit{circuit}_{suffix}"
                assert key in regs, f"{key} missing from before-2016 map"
