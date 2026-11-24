"""The user's electricity price and cost never reach a telemetry payload.

With an electricity price entity configured, the derived-metrics adapter adds
the current tariff and the accumulated cost to the poll data, which feeds both
the metrics points and the register snapshot. Neither describes the heat pump,
and the telemetry documentation does not disclose them.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import re
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.hitachi_yutaki.adapters.derived_metrics import (
    DerivedMetricsAdapter,
)
from custom_components.hitachi_yutaki.const import (
    CONF_ELECTRICITY_PRICE_ENTITY,
    DOMAIN,
)
from custom_components.hitachi_yutaki.telemetry.boundary import (
    NEVER_SENT,
    PRIVATE_KEYS,
    shareable,
)
from homeassistant.core import HomeAssistant

from .domain.clock import FakeClock
from .test_init_telemetry_identity import _make_entry, _setup

pytestmark = pytest.mark.usefixtures("unload_entries")

PRICE_ENTITY = "sensor.electricity_price"


def _priced_poll(hass: HomeAssistant) -> dict:
    """Return a poll enriched by the real adapter with a price entity set."""
    hass.states.async_set(PRICE_ENTITY, "0.2516")
    config_entry = MagicMock()
    config_entry.data = {CONF_ELECTRICITY_PRICE_ENTITY: PRICE_ENTITY}
    adapter = DerivedMetricsAdapter(
        hass=hass,
        config_entry=config_entry,
        power_supply="single",
        clock=FakeClock(),
    )
    data = {
        "is_available": True,
        "outdoor_temp": 5.0,
        "compressor_current": 8.0,
        "is_compressor_running": True,
        "is_defrosting": False,
    }
    adapter.update(data)
    return data


def _mock_session() -> MagicMock:
    resp = AsyncMock()
    resp.status = 202
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock(spec=aiohttp.ClientSession)
    session.post = MagicMock(return_value=ctx)
    return session


def _bodies(session: MagicMock) -> list[dict]:
    return [
        json.loads(gzip.decompress(call.kwargs["data"]))
        for call in session.post.call_args_list
    ]


def test_adapter_private_keys_are_declared(hass: HomeAssistant) -> None:
    """Every key the price entity adds to the poll is declared private."""
    data = _priced_poll(hass)
    assert {"_current_price", "electricity_cost"} <= data.keys()
    assert {"_current_price", "electricity_cost"} <= PRIVATE_KEYS


def test_shareable_drops_never_sent_keys() -> None:
    """The boundary keeps measurements and drops internal and private keys."""
    point = shareable(
        {"outdoor_temp": 5.0, "is_available": True, "_current_price": 0.25}
    )
    assert point == {"outdoor_temp": 5.0}
    assert "is_available" in NEVER_SENT


@pytest.mark.asyncio
async def test_price_and_cost_never_leave_the_instance(hass: HomeAssistant) -> None:
    """Neither the metrics batch nor the register snapshot carries them."""
    session = _mock_session()
    entry = _make_entry(title="PAC", unique_id=f"{DOMAIN}_HW1_1", telemetry="on")
    with patch(
        "custom_components.hitachi_yutaki.async_get_clientsession",
        return_value=session,
    ):
        coordinator = await _setup(hass, entry)
    data = _priced_poll(hass)

    coordinator.telemetry_collector.collect(data)
    assert await coordinator.async_flush_telemetry() is True
    await coordinator._send_register_snapshot(data)

    metrics, snapshot = _bodies(session)
    assert metrics["type"] == "metrics"
    assert snapshot["type"] == "snapshot"
    assert "outdoor_temp" in metrics["points"][0]
    assert "outdoor_temp" in snapshot["registers"]
    for key in PRIVATE_KEYS:
        assert key not in metrics["points"][0]
        assert key not in snapshot["registers"]


def test_worker_drops_the_same_private_keys() -> None:
    """The Worker's defensive deny list matches the integration's boundary."""
    validator = (
        Path(__file__).parent.parent / "backend" / "worker" / "src" / "validator.ts"
    ).read_text(encoding="utf-8")
    match = re.search(r"const PRIVATE_KEYS = new Set\(\[(.*?)\]\);", validator, re.S)
    assert match is not None
    assert set(re.findall(r'"([^"]+)"', match.group(1))) == PRIVATE_KEYS
