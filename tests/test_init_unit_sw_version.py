"""Tests for the Control Unit device's sw_version built from the poll data."""

from __future__ import annotations

from custom_components.hitachi_yutaki import _unit_sw_version


def test_both_numbers_present():
    """PCB and LCD numbers are joined in a fixed order, in Hitachi's H-0xxx form."""
    assert _unit_sw_version({"software_pcb": 289, "software_lcd": 272}) == (
        "PCB H-0289 / LCD H-0272"
    )


def test_number_is_zero_padded_to_four_digits():
    """The LCD shows H-0272 for 272; short numbers pad the same way."""
    assert _unit_sw_version({"software_pcb": 7}) == "PCB H-0007"


def test_single_number_present():
    """A missing half is left out rather than rendered as None."""
    assert _unit_sw_version({"software_pcb": 289}) == "PCB H-0289"
    assert _unit_sw_version({"software_lcd": 272, "software_pcb": None}) == (
        "LCD H-0272"
    )


def test_no_number_present():
    """Without any software number the device keeps no sw_version."""
    assert _unit_sw_version({}) is None
    assert _unit_sw_version({"outdoor_temp": 7}) is None


def test_no_poll_data():
    """A coordinator without data yet (None) yields no sw_version."""
    assert _unit_sw_version(None) is None
