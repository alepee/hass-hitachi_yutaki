"""Tests for the HC-A-MB gateway configuration provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hitachi_yutaki.api.base import ReadResult
from custom_components.hitachi_yutaki.api.config_providers.hc_a_mb import (
    HcAMbConfigProvider,
)
from custom_components.hitachi_yutaki.api.modbus.hc_a_mb.unit_table import (
    parse_unit_table,
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
        client.base_keys = ["system_config", "system_state"]

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


@pytest.mark.asyncio
class TestHcAMbUnitIdentity:
    """The unit's (Ou, Iu) identity is persisted at config time (#476)."""

    async def _process(self, slot_registers: list[int]) -> dict:
        client = MagicMock()
        client.connect = AsyncMock(return_value=True)
        client.close = AsyncMock(return_value=True)
        client.read_values = AsyncMock(return_value=ReadResult.SUCCESS)
        client.read_value = AsyncMock(return_value=0)
        client.decode_config = MagicMock(return_value={})
        client.async_read_unit_table = AsyncMock(
            return_value=parse_unit_table(slot_registers, first_slot=2)
        )
        client.connected = True
        client.base_keys = ["system_config"]

        info = MagicMock()
        info.client_class = MagicMock(return_value=client)

        with patch.dict(
            "custom_components.hitachi_yutaki.api.config_providers.hc_a_mb.GATEWAY_INFO",
            {"modbus_hc_a_mb": info},
        ):
            outcome = await HcAMbConfigProvider().process_step(
                hass=MagicMock(),
                step_id="hc_a_mb_connection",
                user_input={
                    "name": "test",
                    "modbus_host": "127.0.0.1",
                    "modbus_port": 502,
                    "modbus_device_id": 1,
                    "unit_id": 2,
                },
                context={},
            )
        client.async_read_unit_table.assert_awaited_once_with(2, 1)
        return outcome.config_data

    async def test_valid_slot_persists_the_pair(self) -> None:
        """A consistent slot stores both Ou and Iu."""
        config = await self._process([1, 5, 6, 2])
        assert (config["outdoor_cycle"], config["indoor_address"]) == (5, 6)

    async def test_empty_slot_persists_nothing(self) -> None:
        """An empty slot stores no identity."""
        config = await self._process([0, 255, 255, 255])
        assert "outdoor_cycle" not in config
        assert "indoor_address" not in config


class TestHcAMbEntryRules:
    """Config entry rules owned by the HC-A provider (#404, #476)."""

    provider = HcAMbConfigProvider()
    gateway = {"modbus_host": "192.0.2.1", "modbus_port": 502}

    def test_unique_id_suffix_prefers_the_pair(self) -> None:
        """The (Ou, Iu) pair when known, the slot otherwise (entries before #476)."""
        config = {"unit_id": 1, "outdoor_cycle": 7}
        assert self.provider.unique_id_suffix(config) == "1"
        assert self.provider.unique_id_suffix({**config, "indoor_address": 8}) == (
            "c7_i8"
        )

    def test_config_conflict_on_a_used_outdoor_cycle(self) -> None:
        """A second entry on a cycle used on the same gateway is refused."""
        existing = [{**self.gateway, "outdoor_cycle": 0}]
        assert (
            self.provider.config_conflict(
                {**self.gateway, "outdoor_cycle": 0}, existing
            )
            == "outdoor_cycle_in_use"
        )
        assert (
            self.provider.config_conflict(
                {**self.gateway, "outdoor_cycle": 1}, existing
            )
            is None
        )
        assert self.provider.config_conflict(dict(self.gateway), existing) is None

    def test_config_conflict_ignores_other_gateways(self) -> None:
        """The same cycle on another gateway is a different unit."""
        existing = [
            {"modbus_host": "192.0.2.10", "modbus_port": 502, "outdoor_cycle": 0}
        ]
        assert (
            self.provider.config_conflict(
                {**self.gateway, "outdoor_cycle": 0}, existing
            )
            is None
        )

    def test_unit_identity_needs_the_pair(self) -> None:
        """The identity is the (Ou, Iu) pair, unknown until both are recorded."""
        assert self.provider.unit_identity({"outdoor_cycle": 5}) is None
        assert self.provider.unit_identity(
            {"outdoor_cycle": 5, "indoor_address": 6}
        ) == (5, 6)

    def test_diagnostics_show_the_bound_unit(self) -> None:
        """Diagnostics tell which unit the entry is bound to and its slot."""
        data = {"unit_id": 2, "outdoor_cycle": 5, "indoor_address": 6}
        assert self.provider.diagnostics(data) == {
            "slot": 2,
            "outdoor_cycle": 5,
            "indoor_address": 6,
        }
