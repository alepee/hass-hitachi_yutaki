"""Control unit switch descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...const import DEVICE_CONTROL_UNIT
from ..base.switch import HitachiYutakiSwitch, HitachiYutakiSwitchEntityDescription

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_control_unit_switches(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSwitch]:
    """Build control unit switch entities."""
    from ..base.switch import _create_switches

    descriptions = _build_control_unit_switch_descriptions()
    return _create_switches(coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT)


def _build_control_unit_switch_descriptions() -> tuple[
    HitachiYutakiSwitchEntityDescription, ...
]:
    """Build control unit switch descriptions."""
    return (
        HitachiYutakiSwitchEntityDescription(
            key="power",
            name="Power",
            get_fn=lambda api, _: api.get_unit_power(),
            set_fn=lambda api, _, enabled: api.set_unit_power(enabled),
            icon="mdi:power",
        ),
    )
