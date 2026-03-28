"""Tests for the HC-A-MB gateway configuration provider."""

from custom_components.hitachi_yutaki.api.config_providers.hc_a_mb import (
    HcAMbConfigProvider,
)


class TestHcAMbConfigProvider:
    """Tests for HcAMbConfigProvider schema and step ordering."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.provider = HcAMbConfigProvider()

    def test_config_steps_returns_one_step(self) -> None:
        """Verify config_steps returns a single step ID."""
        assert self.provider.config_steps() == ["hc_a_mb_connection"]

    def test_connection_schema_has_unit_id(self) -> None:
        """Verify the connection schema includes the unit_id field."""
        step = self.provider.step_schema("hc_a_mb_connection", {})
        schema_keys = {k.schema for k in step.schema.schema}
        assert "unit_id" in schema_keys

    def test_connection_schema_has_standard_fields(self) -> None:
        """Verify the connection schema includes host, port, device_id, scan_interval, name."""
        step = self.provider.step_schema("hc_a_mb_connection", {})
        schema_keys = {k.schema for k in step.schema.schema}
        assert "modbus_host" in schema_keys
        assert "modbus_port" in schema_keys
        assert "modbus_device_id" in schema_keys
        assert "scan_interval" in schema_keys
        assert "name" in schema_keys
