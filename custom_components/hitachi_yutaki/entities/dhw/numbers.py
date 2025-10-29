"""DHW number descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature

from ...const import DEVICE_DHW
from ..base.number import (
    HitachiYutakiNumber,
    HitachiYutakiNumberEntityDescription,
    _create_numbers,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_dhw_numbers(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiNumber]:
    """Build DHW number entities."""
    descriptions = _build_dhw_number_descriptions()
    return _create_numbers(coordinator, entry_id, descriptions, DEVICE_DHW, "dhw")


def _build_dhw_number_descriptions() -> tuple[
    HitachiYutakiNumberEntityDescription, ...
]:
    """Build DHW number descriptions."""
    return (
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
