"""Pool number descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature

from ...const import DEVICE_POOL
from ..base.number import (
    HitachiYutakiNumber,
    HitachiYutakiNumberEntityDescription,
    _create_numbers,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_pool_numbers(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiNumber]:
    """Build pool number entities."""
    descriptions = _build_pool_number_descriptions()
    return _create_numbers(coordinator, entry_id, descriptions, DEVICE_POOL, "pool")


def _build_pool_number_descriptions() -> tuple[
    HitachiYutakiNumberEntityDescription, ...
]:
    """Build pool number descriptions."""
    return (
        HitachiYutakiNumberEntityDescription(
            key="pool_target_temp",
            translation_key="pool_target_temperature",
            description="Target temperature for swimming pool water",
            native_min_value=0,
            native_max_value=80,
            native_step=1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            get_fn=lambda api, _: api.get_pool_target_temperature(),
            set_fn=lambda api, _, value: api.set_pool_target_temperature(value),
            condition=lambda c: c.has_pool(),
        ),
    )
