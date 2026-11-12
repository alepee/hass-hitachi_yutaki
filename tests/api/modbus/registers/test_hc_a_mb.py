"""Tests for the HC-A(16/64)MB register map."""

import pytest

from custom_components.hitachi_yutaki.api.modbus.registers.codecs import UNSIGNED
from custom_components.hitachi_yutaki.api.modbus.registers.hc_a_mb import (
    HCA_UNIT_MODE,
    UNIT_MODEL,
    HcAMbRegisterMap,
    _compute_base,
)
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
        """Outdoor registers default to base 30000 when no cycle is given (#353)."""
        rmap = HcAMbRegisterMap(unit_id=0)
        regs = rmap.all_registers
        assert regs["compressor_td_discharge_temp"].address == 30001
        assert regs["compressor_te_evaporator_temp"].address == 30002
        assert regs["compressor_current"].address == 30006
        assert regs["compressor_frequency"].address == 30007
        assert regs["compressor_evo_outdoor_expansion_valve_opening"].address == 30008

    def test_outdoor_cycle_none_defaults_to_base(self):
        """outdoor_cycle=None must resolve at base 30000 (preserve old behaviour)."""
        rmap = HcAMbRegisterMap(unit_id=0, outdoor_cycle=None)
        assert rmap.all_registers["compressor_current"].address == 30006

    def test_outdoor_register_addresses_with_cycle(self):
        """Outdoor registers shift by cycle * 100 (section 5.2.3, #353)."""
        rmap = HcAMbRegisterMap(unit_id=1, outdoor_cycle=5)
        regs = rmap.all_registers
        assert regs["compressor_td_discharge_temp"].address == 30501
        assert regs["compressor_te_evaporator_temp"].address == 30502
        assert regs["compressor_current"].address == 30506
        assert regs["compressor_frequency"].address == 30507
        assert regs["compressor_evo_outdoor_expansion_valve_opening"].address == 30508

    def test_outdoor_address_depends_on_cycle_not_unit_id(self):
        """Outdoor addresses key on the cycle, never on the unit_id (#353).

        The cycle is arbitrary: on a real gateway units 0/1/2 mapped to cycles
        0/5/7, so ``unit_id * 100`` would be wrong. A cycle-0 unit_id-2 map
        still resolves at base 30000, while a cycle-7 unit_id-0 map resolves at
        30700.
        """
        rmap_unit2_cycle0 = HcAMbRegisterMap(unit_id=2, outdoor_cycle=0)
        rmap_unit0_cycle7 = HcAMbRegisterMap(unit_id=0, outdoor_cycle=7)
        assert rmap_unit2_cycle0.all_registers["compressor_current"].address == 30006
        assert rmap_unit0_cycle7.all_registers["compressor_current"].address == 30706

    def test_outdoor_register_addresses_independent_of_unit_id(self):
        """Outdoor addresses must NOT shift with unit_id at the same cycle.

        The outdoor block (section 5.2.3) is keyed on the outdoor refrigerant
        cycle, not the indoor unit_id: two maps built with different unit_ids
        but the same (default) cycle share the same outdoor addresses, unlike
        indoor registers which shift by 200 per unit_id.
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

    def test_indoor_block_unaffected_by_cycle(self):
        """Indoor registers still scale with unit_id and ignore outdoor_cycle."""
        rmap = HcAMbRegisterMap(unit_id=1, outdoor_cycle=5)
        # outdoor_temp = 5000 + unit_id * 200 + 142
        assert rmap.all_registers["outdoor_temp"].address == 5342

    def test_register_map_addresses_unit1(self):
        """Verify addresses shift correctly for unit_id=1."""
        rmap = HcAMbRegisterMap(unit_id=1)
        regs = rmap.all_registers
        assert regs["unit_power"].address == 5300
        assert regs["unit_power"].write_address == 5250
        assert regs["system_config"].address == 5340

    def test_software_number_registers(self):
        """Software PCB/LCD sit at STATUS offsets 146/147 of the indoor block."""
        rmap = HcAMbRegisterMap(unit_id=1)
        regs = rmap.all_registers
        assert regs["software_pcb"].address == 5346
        assert regs["software_lcd"].address == 5347
        for key in ("software_pcb", "software_lcd"):
            assert regs[key].write_address is None
            assert key not in rmap.writable_keys
            assert key in rmap.control_unit_keys


class TestHcaUnitModeCodec:
    """Unit mode: STATUS bits on read (offset 101), CONTROL value on write (51)."""

    def test_decode_status_bits(self):
        """B1 set is auto, else B0 is cool (0) / heat (1)."""
        assert HCA_UNIT_MODE.decode(0b00) == 0
        assert HCA_UNIT_MODE.decode(0b01) == 1
        assert HCA_UNIT_MODE.decode(0b10) == 2
        assert HCA_UNIT_MODE.decode(0b11) == 2

    def test_undocumented_word_is_no_mode(self):
        """0xFFFF used to read as auto (#534); garbage is no mode."""
        assert HCA_UNIT_MODE.decode(0xFFFF) is None
        assert HCA_UNIT_MODE.decode(0xFFC0) is None

    def test_encode_control_value(self):
        """Cool and heat are written as is; auto cannot be commanded."""
        assert HCA_UNIT_MODE.encode(0) == 0
        assert HCA_UNIT_MODE.encode(1) == 1
        with pytest.raises(ValueError):
            HCA_UNIT_MODE.encode(2)

    def test_map_uses_it(self):
        """The unit_mode register decodes through the HC-A codec."""
        assert HcAMbRegisterMap().all_registers["unit_mode"].codec is HCA_UNIT_MODE


class TestUnitModelCodec:
    """HC-A documents seven unit models."""

    def test_models(self):
        """Every documented id decodes; others are unknown."""
        assert [UNIT_MODEL.decode(i) for i in range(7)] == [
            "yutaki_s",
            "yutaki_s_combi",
            "yutaki_s80",
            "yutaki_m",
            "yutaki_sc_lite",
            "yutampo_r32",
            "ycc",
        ]
        assert UNIT_MODEL.decode(99) == "unknown"


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
        """HC-A(16/64)MB pool_target_temp is integer °C, not tenths."""
        rmap = HcAMbRegisterMap()
        reg = rmap.all_registers["pool_target_temp"]
        # HC-A(16/64)MB stores pool temp as integer °C, not tenths
        assert reg.codec is UNSIGNED


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


def test_central_control_mode_register():
    """LCD Central Mode sits at indoor offset 139, read-only, a gateway key."""
    reg_map = HcAMbRegisterMap(unit_id=1)
    reg = reg_map.all_registers["central_control_mode"]
    assert reg.address == 5000 + 200 + 139
    assert reg.write_address is None
    assert "central_control_mode" in reg_map.gateway_keys
    assert "central_control_mode" in reg_map.base_keys


def test_mixing_valve_register():
    """Mixing Valve Opening sits at indoor offset 160, read-only, a circuit 2 key."""
    reg_map = HcAMbRegisterMap(unit_id=1)
    reg = reg_map.all_registers["circuit2_mixing_valve_position"]
    assert reg.address == 5000 + 200 + 160
    assert reg.write_address is None
    assert reg.codec.decode(0xFFFF) is None
    assert "circuit2_mixing_valve_position" in reg_map.circuit_2_keys
    assert "circuit2_mixing_valve_position" in reg_map.base_keys
