"""Tests for the ATW-MBS-02 register map."""

from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
    deserialize_otc_method_cooling,
    serialize_otc_method_cooling,
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
            assert reg.deserializer is None
            assert 0xFFFF in reg.sentinel_values
            assert key not in reg_map.writable_keys

    def test_polled_with_control_unit_keys(self):
        """The keys belong to the control unit and are part of every poll."""
        reg_map = AtwMbs02RegisterMap()
        for key in ("software_pcb", "software_lcd"):
            assert key in reg_map.control_unit_keys
            assert key in reg_map.base_keys


class TestDeserializers:
    """Test ATW-MBS-02-specific deserializers."""

    def test_otc_method_cooling(self):
        """Test ATW-MBS-02 cooling OTC method (3 options, no gradient)."""
        assert deserialize_otc_method_cooling(0) == OTCCalculationMethod.DISABLED
        assert deserialize_otc_method_cooling(1) == OTCCalculationMethod.POINTS
        assert deserialize_otc_method_cooling(2) == OTCCalculationMethod.FIX
        assert deserialize_otc_method_cooling(3) is None  # Out of range
        assert deserialize_otc_method_cooling(None) is None

    def test_serialize_otc_method_cooling(self):
        """Test ATW-MBS-02 cooling OTC serializer."""
        assert serialize_otc_method_cooling(OTCCalculationMethod.DISABLED) == 0
        assert serialize_otc_method_cooling(OTCCalculationMethod.POINTS) == 1
        assert serialize_otc_method_cooling(OTCCalculationMethod.FIX) == 2


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
        assert 0xFFFF in reg.sentinel_values
        assert "circuit2_mixing_valve_position" not in reg_map.writable_keys
        assert "circuit2_mixing_valve_position" in reg_map.circuit_2_keys
        assert "circuit2_mixing_valve_position" in reg_map.base_keys
