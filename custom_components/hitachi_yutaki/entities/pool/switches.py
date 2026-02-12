"""Pool switch descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...const import DEVICE_POOL
from ..base.switch import (
    HitachiYutakiSwitch,
    HitachiYutakiSwitchEntityDescription,
    _create_switches,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_pool_switches(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSwitch]:
    """Build pool switch entities."""
    descriptions = _build_pool_switch_descriptions()
    return _create_switches(coordinator, entry_id, descriptions, DEVICE_POOL, "pool")


def _build_pool_switch_descriptions() -> tuple[
    HitachiYutakiSwitchEntityDescription, ...
]:
    """Build pool switch descriptions."""
    return (
        HitachiYutakiSwitchEntityDescription(
            key="power",
            name="Power",
            icon="mdi:power",
            condition=lambda c: c.has_pool(),
            get_fn=lambda api, _: api.get_pool_power(),
            set_fn=lambda api, _, enabled: api.set_pool_power(enabled),
        ),
    )
