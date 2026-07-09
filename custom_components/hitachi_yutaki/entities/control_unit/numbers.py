"""Control unit number descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory

from ...const import DEVICE_CONTROL_UNIT
from ..base.number import (
    HitachiYutakiNumber,
    HitachiYutakiNumberEntityDescription,
    _create_numbers,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_control_unit_numbers(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiNumber]:
    """Build control unit number entities."""
    descriptions = (
        HitachiYutakiNumberEntityDescription(
            key="eco_offset",
            translation_key="eco_offset",
            native_min_value=0,
            native_max_value=255,
            native_step=1,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            get_fn=lambda api, _: (
                float(v) if (v := api.get_eco_offset()) is not None else None
            ),
            set_fn=None,
            condition=lambda c: (
                "eco_offset" in c.api_client.register_map.all_registers
            ),
        ),
    )
    return _create_numbers(
        coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT, "control_unit"
    )
