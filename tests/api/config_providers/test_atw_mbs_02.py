"""Tests for the ATW-MBS-02 gateway configuration provider."""

import pytest

from custom_components.hitachi_yutaki.api.config_providers.atw_mbs_02 import (
    AtwMbs02ConfigProvider,
)


class TestAtwMbs02ConfigProvider:
    """Tests for AtwMbs02ConfigProvider schema and step ordering."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.provider = AtwMbs02ConfigProvider()

    def test_config_steps_returns_two_steps(self) -> None:
        """Verify config_steps returns the two expected step IDs in order."""
        assert self.provider.config_steps() == [
            "atw_mbs_02_connection",
            "atw_mbs_02_variant",
        ]

    def test_connection_schema_has_required_fields(self) -> None:
        """Verify the connection schema contains all expected fields."""
        step = self.provider.step_schema("atw_mbs_02_connection", {})
        schema_keys = {k.schema for k in step.schema.schema}
        assert "modbus_host" in schema_keys
        assert "modbus_port" in schema_keys
        assert "modbus_device_id" in schema_keys
        assert "scan_interval" in schema_keys
        assert "name" in schema_keys

    def test_connection_schema_has_no_unit_id(self) -> None:
        """Explicitly verify unit_id is not in the connection schema."""
        step = self.provider.step_schema("atw_mbs_02_connection", {})
        schema_keys = {k.schema for k in step.schema.schema}
        assert "unit_id" not in schema_keys

    def test_variant_schema_has_gateway_variant_field(self) -> None:
        """Verify the variant schema contains the gateway_variant field."""
        step = self.provider.step_schema("atw_mbs_02_variant", {})
        schema_keys = {k.schema for k in step.schema.schema}
        assert "gateway_variant" in schema_keys

    def test_variant_schema_includes_auto_detection_placeholder(self) -> None:
        """Verify description_placeholders when a variant was detected."""
        context = {"_detected_variant": "gen2"}
        step = self.provider.step_schema("atw_mbs_02_variant", context)
        assert "detected_variant" in step.description_placeholders
        assert "model_decoder_url" in step.description_placeholders
        # gen2 -> "Gen 2"
        assert step.description_placeholders["detected_variant"] == "Gen 2"

    def test_variant_schema_handles_no_detection(self) -> None:
        """Verify detected_variant placeholder is '?' when no variant detected."""
        context = {"_detected_variant": ""}
        step = self.provider.step_schema("atw_mbs_02_variant", context)
        assert step.description_placeholders["detected_variant"] == "?"

    def test_unknown_step_raises(self) -> None:
        """Verify step_schema raises ValueError for an unknown step ID."""
        with pytest.raises(ValueError, match="Unknown step_id"):
            self.provider.step_schema("invalid", {})
