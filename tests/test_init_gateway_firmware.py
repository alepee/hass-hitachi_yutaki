"""Tests for the Gateway device's hw/sw version built from the poll data."""

from __future__ import annotations

from custom_components.hitachi_yutaki import _version_text


def test_reported_version_becomes_text():
    """A polled version number is rendered as plain text."""
    data = {"gateway_hw_version": 12, "gateway_sw_version": 103}
    assert _version_text(data, "gateway_hw_version") == "12"
    assert _version_text(data, "gateway_sw_version") == "103"


def test_missing_version_yields_none():
    """A key the map does not define, or a filtered read, leaves no version."""
    assert _version_text({"outdoor_temp": 7}, "gateway_sw_version") is None
    assert _version_text({"gateway_sw_version": None}, "gateway_sw_version") is None


def test_no_poll_data():
    """A coordinator without data yet (None) yields no version."""
    assert _version_text(None, "gateway_sw_version") is None
