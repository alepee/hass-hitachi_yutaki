"""Tests for the HC-A(16/64)MB register map."""

from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.hc_a_mb import (
    HcAMbRegisterMap,
    _compute_base,
    convert_from_tenths,
    convert_signed_16bit,
    deserialize_otc_method_cooling,
    deserialize_unit_mode_status,
    deserialize_unit_model,
    serialize_otc_method_cooling,
)
from custom_components.hitachi_yutaki.const import OTCCalculationMethod
from custom_components.hitachi_yutaki.profiles import PROFILES
from custom_components.hitachi_yutaki.profiles.yutaki_s_combi import (
    YutakiSCombiProfile,
)


class TestAddressComputation:
    """Test base address computation for various unit IDs."""

    def test_unit_id_0(self):
        """Unit ID 0 should have base address 5000."""
        assert _compute_base(0) == 5000

    def test_unit_id_1(self):
        """Unit ID 1 should have base address 5200."""
        assert _compute_base(1) == 5200

    def test_unit_id_15(self):
        """Unit ID 15 should have base address 8000."""
        assert _compute_base(15) == 8000

    def test_register_map_addresses_unit0(self):
        """Verify key addresses for unit_id=0."""
        rmap = HcAMbRegisterMap(unit_id=0)
        regs = rmap.all_registers
        # STATUS registers
        assert regs["unit_power"].address == 5100
        assert regs["unit_mode"].address == 5101
        assert regs["system_config"].address == 5140
        assert regs["operation_state"].address == 5141
        assert regs["outdoor_temp"].address == 5142
        assert regs["alarm_code"].address == 5167
        # CONTROL (write) addresses
        assert regs["unit_power"].write_address == 5050
        assert regs["unit_mode"].write_address == 5051

    def test_outdoor_register_addresses(self):
        """Verify outdoor unit registers use fixed base 30000 (section 5.3)."""
        rmap = HcAMbRegisterMap(unit_id=0)
        regs = rmap.all_registers
        assert regs["compressor_td_discharge_temp"].address == 30001
        assert regs["compressor_te_evaporator_temp"].address == 30002
        assert regs["compressor_current"].address == 30006
        assert regs["compressor_frequency"].address == 30007
        assert regs["compressor_evo_outdoor_expansion_valve_opening"].address == 30008

    def test_outdoor_register_addresses_independent_of_unit_id(self):
        """Outdoor unit addresses must NOT shift with unit_id.

        The outdoor unit block (section 5.3) is shared across all indoor units
        and uses a fixed base address of 30000, unlike indoor unit registers
        which shift by 200 per unit_id.
        """
        rmap_unit0 = HcAMbRegisterMap(unit_id=0)
        rmap_unit1 = HcAMbRegisterMap(unit_id=1)
        outdoor_keys = [
            "compressor_td_discharge_temp",
            "compressor_te_evaporator_temp",
            "compressor_current",
            "compressor_frequency",
            "compressor_evo_outdoor_expansion_valve_opening",
        ]
        for key in outdoor_keys:
            assert (
                rmap_unit0.all_registers[key].address
                == rmap_unit1.all_registers[key].address
            ), f"{key} address should not change with unit_id"

    def test_register_map_addresses_unit1(self):
        """Verify addresses shift correctly for unit_id=1."""
        rmap = HcAMbRegisterMap(unit_id=1)
        regs = rmap.all_registers
        assert regs["unit_power"].address == 5300
        assert regs["unit_power"].write_address == 5250
        assert regs["system_config"].address == 5340


class TestDeserializers:
    """Test HC-A(16/64)MB-specific deserializers."""

    def test_unit_model_standard(self):
        """Test standard model IDs."""
        assert deserialize_unit_model(0) == "yutaki_s"
        assert deserialize_unit_model(1) == "yutaki_s_combi"
        assert deserialize_unit_model(2) == "yutaki_s80"
        assert deserialize_unit_model(3) == "yutaki_m"

    def test_unit_model_hc_a_mb_only(self):
        """Test HC-A(16/64)MB-specific model IDs."""
        assert deserialize_unit_model(4) == "yutaki_sc_lite"
        assert deserialize_unit_model(5) == "yutampo_r32"
        assert deserialize_unit_model(6) == "ycc"

    def test_unit_model_unknown(self):
        """Test unknown model ID."""
        assert deserialize_unit_model(99) == "unknown"
        assert deserialize_unit_model(None) == "unknown"

    def test_unit_mode_status_cool(self):
        """B0=0, B1=0 → Cool (0)."""
        assert deserialize_unit_mode_status(0b00) == 0

    def test_unit_mode_status_heat(self):
        """B0=1, B1=0 → Heat (1)."""
        assert deserialize_unit_mode_status(0b01) == 1

    def test_unit_mode_status_auto_cool(self):
        """B0=0, B1=1 → Auto (2)."""
        assert deserialize_unit_mode_status(0b10) == 2

    def test_unit_mode_status_auto_heat(self):
        """B0=1, B1=1 → Auto (2)."""
        assert deserialize_unit_mode_status(0b11) == 2

    def test_unit_mode_status_none(self):
        """None input should return None."""
        assert deserialize_unit_mode_status(None) is None

    def test_otc_method_cooling(self):
        """Test HC-A(16/64)MB cooling OTC method (3 options, no gradient)."""
        assert deserialize_otc_method_cooling(0) == OTCCalculationMethod.DISABLED
        assert deserialize_otc_method_cooling(1) == OTCCalculationMethod.POINTS
        assert deserialize_otc_method_cooling(2) == OTCCalculationMethod.FIX
        assert deserialize_otc_method_cooling(3) is None  # Out of range
        assert deserialize_otc_method_cooling(None) is None

    def test_serialize_otc_method_cooling(self):
        """Test cooling OTC serializer."""
        assert serialize_otc_method_cooling(OTCCalculationMethod.DISABLED) == 0
        assert serialize_otc_method_cooling(OTCCalculationMethod.POINTS) == 1
        assert serialize_otc_method_cooling(OTCCalculationMethod.FIX) == 2

    def test_convert_signed_16bit_positive(self):
        """Test positive value."""
        assert convert_signed_16bit(25) == 25

    def test_convert_signed_16bit_negative(self):
        """Test negative temperature (2's complement)."""
        assert convert_signed_16bit(65531) == -5  # 0xFFFB

    def test_convert_signed_16bit_none(self):
        """None returns None."""
        assert convert_signed_16bit(None) is None

    def test_convert_signed_16bit_sensor_error(self):
        """0xFFFF should return None (sensor error)."""
        assert convert_signed_16bit(0xFFFF) is None

    def test_convert_from_tenths(self):
        """Test tenths conversion."""
        assert convert_from_tenths(250) == 25.0
        assert convert_from_tenths(None) is None
        assert convert_from_tenths(0xFFFF) is None


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


class TestWriteAddressResolution:
    """Test that write_address is correctly resolved."""

    def test_registers_with_write_address(self):
        """Registers with write_address should have different read/write addresses."""
        rmap = HcAMbRegisterMap()
        reg = rmap.all_registers["unit_power"]
        assert reg.address != reg.write_address
        assert reg.address == 5100  # STATUS
        assert reg.write_address == 5050  # CONTROL

    def test_read_only_registers(self):
        """Read-only registers should have no write_address."""
        rmap = HcAMbRegisterMap()
        reg = rmap.all_registers["outdoor_temp"]
        assert reg.write_address is None

    def test_pool_target_temp_no_tenths(self):
        """HC-A(16/64)MB pool_target_temp should NOT have convert_from_tenths."""
        rmap = HcAMbRegisterMap()
        reg = rmap.all_registers["pool_target_temp"]
        # HC-A(16/64)MB stores pool temp as integer °C, not tenths
        assert reg.deserializer is None


class TestBitMasks:
    """Test bit mask values."""

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


class TestProfileDetectionWithHcAMb:
    """Test that profile detection works with HC-A(16/64)MB model names."""

    def test_yutampo_direct_detection(self):
        """Yutampo should be detected by direct model name from HC-A(16/64)MB."""
        data = {"unit_model": "yutampo_r32"}
        matching = [key for key, profile in PROFILES.items() if profile.detect(data)]
        assert len(matching) == 1
        assert matching[0] == "yutampo_r32"

    def test_yutaki_sc_lite_detection(self):
        """Yutaki SC Lite should be detected."""
        data = {"unit_model": "yutaki_sc_lite"}
        matching = [key for key, profile in PROFILES.items() if profile.detect(data)]
        assert len(matching) == 1
        assert matching[0] == "yutaki_sc_lite"

    def test_ycc_detection(self):
        """YCC should be detected."""
        data = {"unit_model": "ycc"}
        matching = [key for key, profile in PROFILES.items() if profile.detect(data)]
        assert len(matching) == 1
        assert matching[0] == "ycc"

    def test_yutampo_heuristic_still_works(self):
        """Yutampo should still be detected via heuristic (ATW-MBS-02 path)."""
        data = {
            "unit_model": "yutaki_s_combi",
            "has_dhw": True,
            "has_circuit1_heating": False,
            "has_circuit1_cooling": False,
            "has_circuit2_heating": False,
            "has_circuit2_cooling": False,
        }
        matching = [key for key, profile in PROFILES.items() if profile.detect(data)]
        assert len(matching) == 1
        assert matching[0] == "yutampo_r32"

    def test_yutampo_direct_does_not_match_s_combi(self):
        """Direct yutampo model name should not match S Combi profile."""
        data = {"unit_model": "yutampo_r32", "has_circuit1_heating": True}
        assert YutakiSCombiProfile.detect(data) is False
