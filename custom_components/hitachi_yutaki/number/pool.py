"""Pool number descriptions."""

from __future__ import annotations

from typing import Final

from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature

from .base import HitachiYutakiNumberEntityDescription

POOL_NUMBERS: Final[tuple[HitachiYutakiNumberEntityDescription, ...]] = (
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
