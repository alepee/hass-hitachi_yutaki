"""Tests for the ATW-MBS-02 gateway configuration provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hitachi_yutaki.api.base import ReadResult
from custom_components.hitachi_yutaki.api.config_providers.atw_mbs_02 import (
    AtwMbs02ConfigProvider,
)


def _make_mock_client(read_result: ReadResult) -> MagicMock:
    """Build a fake API client whose read_values returns the given ReadResult."""
    client = MagicMock()
    client.connect = AsyncMock(return_value=True)
    client.close = AsyncMock(return_value=True)
    client.read_values = AsyncMock(return_value=read_result)
    client.read_value = AsyncMock(return_value=None)
    client.connected = True
    client.register_map = MagicMock(
        base_keys=["system_config", "system_state"],
        gateway_keys=["unit_model", "system_state"],
    )
    return client


def _patch_client_class(client: MagicMock):
    """Patch GATEWAY_INFO so the provider instantiates `client` instead of the real class."""
    info = MagicMock()
    info.client_class = MagicMock(return_value=client)
    return patch.dict(
        "custom_components.hitachi_yutaki.api.config_providers.atw_mbs_02.GATEWAY_INFO",
        {"modbus_atw_mbs_02": info},
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


@pytest.mark.asyncio
class TestAtwMbs02GatewayNotReady:
    """Regression: provider must not crash when gateway is initializing/desynced.

    Before the fix, read_values returning GATEWAY_NOT_READY left _data empty,
    read_value returned None for every key, and decode_config crashed with
    `TypeError: unsupported operand type(s) for &: 'NoneType' and 'int'`.
    """

    async def test_detect_profiles_returns_gateway_not_ready(self) -> None:
        """_detect_profiles must surface gateway_not_ready, not crash."""
        client = _make_mock_client(ReadResult.GATEWAY_NOT_READY)
        with _patch_client_class(client):
            (
                detected,
                system_config,
                error,
            ) = await AtwMbs02ConfigProvider._detect_profiles(
                hass=MagicMock(),
                context={
                    "name": "test",
                    "modbus_host": "127.0.0.1",
                    "modbus_port": 502,
                    "modbus_device_id": 1,
                },
                variant="gen2",
            )
        assert detected == []
        assert system_config == 0
        assert error == "gateway_not_ready"
        client.read_value.assert_not_called()  # short-circuit before decode

    async def test_test_connection_returns_gateway_not_ready(self) -> None:
        """_test_connection must distinguish gateway_not_ready from cannot_connect."""
        client = _make_mock_client(ReadResult.GATEWAY_NOT_READY)
        with _patch_client_class(client):
            ok, error = await AtwMbs02ConfigProvider._test_connection(
                hass=MagicMock(),
                config={
                    "name": "test",
                    "modbus_host": "127.0.0.1",
                    "modbus_port": 502,
                    "modbus_device_id": 1,
                },
            )
        assert ok is False
        assert error == "gateway_not_ready"

    async def test_detect_variant_returns_none_when_gateway_not_ready(self) -> None:
        """_detect_variant must skip auto-detect when gateway is not ready."""
        client = _make_mock_client(ReadResult.GATEWAY_NOT_READY)
        with _patch_client_class(client):
            variant = await AtwMbs02ConfigProvider._detect_variant(
                hass=MagicMock(),
                config={
                    "modbus_host": "127.0.0.1",
                    "modbus_port": 502,
                    "modbus_device_id": 1,
                },
            )
        assert variant is None
        client.read_value.assert_not_called()
