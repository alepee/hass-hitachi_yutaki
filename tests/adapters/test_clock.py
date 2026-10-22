"""Test the infrastructure clock's HA timezone boundary."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from custom_components.hitachi_yutaki.adapters.clock import HomeAssistantClock


def test_clock_uses_configured_ha_timezone(monkeypatch):
    """HA's next calendar day is independent of the host OS timezone."""
    hass = MagicMock()
    hass.config.time_zone = "Asia/Tokyo"
    monkeypatch.setattr(
        "custom_components.hitachi_yutaki.adapters.clock.dt_util.utcnow",
        lambda: datetime(2026, 1, 1, 16, tzinfo=UTC),
    )
    clock = HomeAssistantClock(hass)
    assert clock.now().isoformat() == "2026-01-02T01:00:00+09:00"
