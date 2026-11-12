"""Tests for the ATW-MBS-02 register map."""

from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    UNIT_MODE,
    AtwMbs02RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02_pre2016 import (
    AtwMbs02Pre2016RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.codecs import (
    OTC_METHOD_COOLING,
    SIGNED,
    UNSIGNED,
)
from custom_components.hitachi_yutaki.const import OTCCalculationMethod


class TestSoftwareNumberRegisters:
    """Unit software numbers (PMML0419 rev.3 p.22, 2016 map)."""

    def test_addresses(self):
        """Software PCB is at 1095, Software LCD at 1096."""
        regs = AtwMbs02RegisterMap().all_registers
        assert regs["software_pcb"].address == 1095
        assert regs["software_lcd"].address == 1096

    def test_read_only(self):
        """Both registers are read-only and filter the 0xFFFF garbage read."""
        reg_map = AtwMbs02RegisterMap()
        for key in ("software_pcb", "software_lcd"):
            reg = reg_map.all_registers[key]
            assert reg.write_address is None
            assert reg.codec is UNSIGNED
            assert reg.codec.decode(0xFFFF) is None
            assert key not in reg_map.writable_keys

    def test_polled_with_control_unit_keys(self):
        """The keys belong to the control unit and are part of every poll."""
        reg_map = AtwMbs02RegisterMap()
        for key in ("software_pcb", "software_lcd"):
            assert key in reg_map.control_unit_keys
            assert key in reg_map.base_keys


class TestRegisterTypes:
    """Each register decodes through the codec of its documented type."""

    def test_outdoor_temp_reads_minus_one(self):
        """Signed temperatures keep -1 °C (#533)."""
        for reg_map in (AtwMbs02RegisterMap(), AtwMbs02Pre2016RegisterMap()):
            reg = reg_map.all_registers["outdoor_temp"]
            assert reg.codec is SIGNED
            assert reg.codec.decode(0xFFFF) == -1

    def test_water_outlet_hp_is_unsigned_with_signed_fallback(self):
        """HP-level outlet is unsigned 0~100 °C; the circuit outlet is signed."""
        for reg_map in (AtwMbs02RegisterMap(), AtwMbs02Pre2016RegisterMap()):
            reg = reg_map.all_registers["water_outlet_temp"]
            assert reg.codec is UNSIGNED
            assert reg.fallback is not None
            assert reg.fallback.codec is SIGNED

    def test_unit_mode_is_a_closed_list(self):
        """A garbage word (0xFFC0 seen in the fleet) is no mode, not a value."""
        reg = AtwMbs02RegisterMap().all_registers["unit_mode"]
        assert reg.codec is UNIT_MODE
        assert [reg.codec.decode(raw) for raw in (0, 1, 2)] == [0, 1, 2]
        assert reg.codec.decode(0xFFC0) is None

    def test_cooling_otc_has_no_gradient(self):
        """Cooling OTC documents 0 disabled, 1 points, 2 fix."""
        reg = AtwMbs02RegisterMap().all_registers[
            "circuit1_otc_calculation_method_cooling"
        ]
        assert reg.codec is OTC_METHOD_COOLING
        assert reg.codec.decode(2) == OTCCalculationMethod.FIX
        assert reg.codec.decode(3) is None


class TestDocumentedDiagnosticRegisters:
    """Central mode and mixing valve position (PMML0419 rev.3, 2016 map)."""

    def test_central_control_mode(self):
        """Central Mode is at 1088, read-only, a gateway key in every poll."""
        reg_map = AtwMbs02RegisterMap()
        reg = reg_map.all_registers["central_control_mode"]
        assert reg.address == 1088
        assert reg.write_address is None
        assert "central_control_mode" in reg_map.gateway_keys
        assert "central_control_mode" in reg_map.base_keys

    def test_mixing_valve_position(self):
        """MVP is at 1216, read-only, 0xFFFF filtered, a circuit 2 key."""
        reg_map = AtwMbs02RegisterMap()
        reg = reg_map.all_registers["circuit2_mixing_valve_position"]
        assert reg.address == 1216
        assert reg.write_address is None
        assert reg.codec.decode(0xFFFF) is None
        assert "circuit2_mixing_valve_position" not in reg_map.writable_keys
        assert "circuit2_mixing_valve_position" in reg_map.circuit_2_keys
        assert "circuit2_mixing_valve_position" in reg_map.base_keys
