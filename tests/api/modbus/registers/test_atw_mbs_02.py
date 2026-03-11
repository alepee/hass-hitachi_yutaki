"""Tests for the ATW-MBS-02 register map."""

from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    deserialize_otc_method_cooling,
    serialize_otc_method_cooling,
)
from custom_components.hitachi_yutaki.const import OTCCalculationMethod


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
