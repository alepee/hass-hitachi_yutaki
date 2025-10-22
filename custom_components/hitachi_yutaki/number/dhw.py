"""DHW number descriptions."""

from __future__ import annotations

from typing import Final

from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature

from .base import HitachiYutakiNumberEntityDescription

DHW_NUMBERS: Final[tuple[HitachiYutakiNumberEntityDescription, ...]] = (
    HitachiYutakiNumberEntityDescription(
        key="antilegionella_temp",
        translation_key="antilegionella_temp",
        description="Target temperature for anti-legionella treatment",
        native_min_value=60,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_fn=lambda api, _: api.get_dhw_antilegionella_temperature(),
        set_fn=lambda api, _, value: api.set_dhw_antilegionella_temperature(value),
        condition=lambda c: c.has_dhw(),
    ),
)
