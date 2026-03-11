"""Cross-gateway compatibility tests between ATW-MBS-02 and HC-A(16/64)MB."""

from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.hc_a_mb import (
    HcAMbRegisterMap,
)


class TestKeyNamingCompatibility:
    """Test that HC-A(16/64)MB uses the same key names as ATW-MBS-02."""

    def test_shared_gateway_keys(self):
        """Essential gateway keys should exist in both maps."""
        atw = AtwMbs02RegisterMap()
        hca = HcAMbRegisterMap()

        # These keys must be present in both
        shared_keys = [
            "alarm_code",
            "unit_model",
            "system_config",
            "system_status",
            "system_state",
        ]
        for key in shared_keys:
            assert key in atw.all_registers, f"{key} missing from ATW-MBS-02"
            assert key in hca.all_registers, f"{key} missing from HC-A(16/64)MB"

    def test_shared_control_unit_keys(self):
        """Essential control unit keys should exist in both maps."""
        atw = AtwMbs02RegisterMap()
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
            assert key in hca.all_registers, f"{key} missing from HC-A(16/64)MB"

    def test_shared_circuit_keys(self):
        """Essential circuit keys should exist in both maps."""
        atw = AtwMbs02RegisterMap()
        hca = HcAMbRegisterMap()

        for circuit in [1, 2]:
            shared_keys = [
                f"circuit{circuit}_power",
                f"circuit{circuit}_target_temp",
                f"circuit{circuit}_current_temp",
                f"circuit{circuit}_eco_mode",
                f"circuit{circuit}_otc_calculation_method_heating",
                f"circuit{circuit}_otc_calculation_method_cooling",
            ]
            for key in shared_keys:
                assert key in atw.all_registers, f"{key} missing from ATW-MBS-02"
                assert key in hca.all_registers, f"{key} missing from HC-A(16/64)MB"

    def test_shared_dhw_keys(self):
        """Essential DHW keys should exist in both maps."""
        atw = AtwMbs02RegisterMap()
        hca = HcAMbRegisterMap()

        shared_keys = [
            "dhw_power",
            "dhw_target_temp",
            "dhw_boost",
            "dhw_high_demand",
            "dhw_current_temp",
        ]
        for key in shared_keys:
            assert key in atw.all_registers, f"{key} missing from ATW-MBS-02"
            assert key in hca.all_registers, f"{key} missing from HC-A(16/64)MB"

    def test_shared_pool_keys(self):
        """Essential pool keys should exist in both maps."""
        atw = AtwMbs02RegisterMap()
        hca = HcAMbRegisterMap()

        shared_keys = ["pool_power", "pool_target_temp", "pool_current_temp"]
        for key in shared_keys:
            assert key in atw.all_registers, f"{key} missing from ATW-MBS-02"
            assert key in hca.all_registers, f"{key} missing from HC-A(16/64)MB"

    def test_shared_primary_compressor_keys(self):
        """All 8 primary compressor keys should exist in both maps."""
        atw = AtwMbs02RegisterMap()
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
            assert key in hca.all_registers, f"{key} missing from HC-A(16/64)MB"

    def test_writable_keys_subset(self):
        """HC-A(16/64)MB writable keys should be a subset of all_registers keys."""
        hca = HcAMbRegisterMap()
        for key in hca.writable_keys:
            assert key in hca.all_registers, f"Writable key {key} not in all_registers"


class TestBitMasks:
    """Test bit mask values across gateways."""

    def test_circuit_masks_identical(self):
        """Circuit bit masks should match ATW-MBS-02."""
        atw = AtwMbs02RegisterMap()
        hca = HcAMbRegisterMap()
        assert atw.masks_circuit == hca.masks_circuit

    def test_status_masks_identical_base(self):
        """Base status masks (bits 0-9) should match ATW-MBS-02."""
        atw = AtwMbs02RegisterMap()
        hca = HcAMbRegisterMap()
        assert atw.mask_defrost == hca.mask_defrost
        assert atw.mask_solar == hca.mask_solar
        assert atw.mask_pump1 == hca.mask_pump1
        assert atw.mask_compressor == hca.mask_compressor
        assert atw.mask_boiler == hca.mask_boiler
        assert atw.mask_dhw_heater == hca.mask_dhw_heater
        assert atw.mask_smart_function == hca.mask_smart_function

    def test_hvac_mode_auto_not_supported_for_write(self):
        """HC-A(16/64)MB should return None for auto mode (can't write auto)."""
        hca = HcAMbRegisterMap()
        assert hca.hvac_unit_mode_auto is None
        assert hca.hvac_unit_mode_cool == 0
        assert hca.hvac_unit_mode_heat == 1
