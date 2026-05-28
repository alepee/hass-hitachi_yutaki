"""Tests for the HC-A-MB gateway configuration provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hitachi_yutaki.api.base import ReadResult
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


@pytest.mark.asyncio
class TestHcAMbGatewayNotReady:
    """Regression: process_step must surface gateway_not_ready instead of crashing.

    Same root cause as ATW-MBS-02: read_values returning GATEWAY_NOT_READY
    leaves _data empty, decode_config(None) would crash.
    """

    async def test_process_step_returns_gateway_not_ready(self) -> None:
        """process_step must return an error outcome when gateway is not ready."""
        client = MagicMock()
        client.connect = AsyncMock(return_value=True)
        client.close = AsyncMock(return_value=True)
        client.read_values = AsyncMock(return_value=ReadResult.GATEWAY_NOT_READY)
        client.read_value = AsyncMock(return_value=None)
        client.connected = True
        client.register_map = MagicMock(base_keys=["system_config", "system_state"])

        info = MagicMock()
        info.client_class = MagicMock(return_value=client)

        provider = HcAMbConfigProvider()
        with patch.dict(
            "custom_components.hitachi_yutaki.api.config_providers.hc_a_mb.GATEWAY_INFO",
            {"modbus_hc_a_mb": info},
        ):
            outcome = await provider.process_step(
                hass=MagicMock(),
                step_id="hc_a_mb_connection",
                user_input={
                    "name": "test",
                    "modbus_host": "127.0.0.1",
                    "modbus_port": 502,
                    "modbus_device_id": 1,
                    "unit_id": 0,
                },
                context={},
            )

        assert outcome.errors == {"base": "gateway_not_ready"}
        assert outcome.detected_profiles is None or outcome.detected_profiles == []
        client.read_value.assert_not_called()
