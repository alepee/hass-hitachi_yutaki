"""Tests for the version-gated parent link of registered devices."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki import _via
from custom_components.hitachi_yutaki.const import DOMAIN
from homeassistant.helpers import device_registry as dr

_MODULE = "custom_components.hitachi_yutaki"


def _parent() -> MagicMock:
    parent = MagicMock()
    parent.id = "abc123"
    parent.identifiers = {("hitachi_yutaki", "entry_gateway")}
    return parent


def test_recent_ha_links_by_device_id():
    """HA 2026.8+ takes the parent's registry id, not its identifier."""
    with patch(f"{_MODULE}._HAS_VIA_DEVICE_ID", True):
        assert _via(_parent()) == {"via_device_id": "abc123"}


def test_older_ha_links_by_identifier():
    """Before 2026.8 only the identifier-based `via_device` exists."""
    with patch(f"{_MODULE}._HAS_VIA_DEVICE_ID", False):
        assert _via(_parent()) == {"via_device": ("hitachi_yutaki", "entry_gateway")}


async def test_child_is_linked_to_parent_in_registry(hass):
    """On whichever HA version runs the suite, the link lands in the registry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)

    gateway = registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "gateway")}
    )
    control_unit = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "control_unit")},
        **_via(gateway),
    )

    assert control_unit.via_device_id == gateway.id
