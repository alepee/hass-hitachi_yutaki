"""Tests for config entry diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.hitachi_yutaki.diagnostics import (
    async_get_config_entry_diagnostics,
)


@pytest.mark.asyncio
async def test_diagnostics_expose_the_unit_identity_and_redact_the_host() -> None:
    """The unit section shows which machine the entry is bound to (#476)."""
    entry = MagicMock()
    entry.data = {
        "gateway_type": "modbus_hc_a_mb",
        "profile": "yutampo_r32",
        "modbus_host": "192.0.2.10",
        "unit_id": 2,
        "outdoor_cycle": 5,
        "indoor_address": 6,
    }
    entry.options = {}
    entry.runtime_data = MagicMock(
        last_update_success=True, system_config=1, data={"system_state": 0}
    )

    diag = await async_get_config_entry_diagnostics(MagicMock(), entry)

    assert diag["unit"] == {
        "gateway_type": "modbus_hc_a_mb",
        "profile": "yutampo_r32",
        "slot": 2,
        "outdoor_cycle": 5,
        "indoor_address": 6,
    }
    assert diag["entry"]["data"]["modbus_host"] == "**REDACTED**"
