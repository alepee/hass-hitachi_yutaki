"""DHW switch descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...const import DEVICE_DHW
from ..base.switch import (
    HitachiYutakiSwitch,
    HitachiYutakiSwitchEntityDescription,
    _create_switches,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_dhw_switches(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSwitch]:
    """Build DHW switch entities."""
    descriptions = _build_dhw_switch_descriptions()
    return _create_switches(coordinator, entry_id, descriptions, DEVICE_DHW, "dhw")


def _build_dhw_switch_descriptions() -> tuple[
    HitachiYutakiSwitchEntityDescription, ...
]:
    """Build DHW switch descriptions."""
    return (
        HitachiYutakiSwitchEntityDescription(
            key="boost",
            name="Boost",
            icon="mdi:flash",
            condition=lambda c: c.has_dhw(),
            get_fn=lambda api, _: api.get_dhw_boost(),
            set_fn=lambda api, _, enabled: api.set_dhw_boost(enabled),
        ),
    )
