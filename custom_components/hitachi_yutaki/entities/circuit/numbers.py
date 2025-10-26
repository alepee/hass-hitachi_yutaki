"""Circuit number descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.hitachi_yutaki.const import (
    CIRCUIT_IDS,
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    DEVICE_TYPES,
)
from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature

from ..base.number import (
    HitachiYutakiNumber,
    HitachiYutakiNumberEntityDescription,
    _create_numbers,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_circuit_numbers(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    circuit_id: CIRCUIT_IDS,
    device_type: DEVICE_TYPES,
) -> list[HitachiYutakiNumber]:
    """Build circuit number entities."""
    descriptions = _build_circuit_number_descriptions(circuit_id)
    return _create_numbers(
        coordinator, entry_id, descriptions, device_type, f"circuit{circuit_id}"
    )


def _build_circuit_number_descriptions(
    circuit_id: CIRCUIT_IDS,
) -> tuple[HitachiYutakiNumberEntityDescription, ...]:
    """Build circuit number descriptions."""
    return (
        HitachiYutakiNumberEntityDescription(
            key="max_flow_temp_heating_otc",
            translation_key="max_flow_temp_heating_otc",
            description="Maximum heating water temperature used in outdoor temperature compensation (OTC) calculations",
            native_min_value=0,
            native_max_value=80,
            native_step=1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
            condition=lambda coordinator: coordinator.has_circuit(
                circuit_id, CIRCUIT_MODE_HEATING
            ),
            get_fn=lambda api, circuit_id: api.get_circuit_max_flow_temp_heating(
                circuit_id
            ),
            set_fn=lambda api, circuit_id, value: api.set_circuit_max_flow_temp_heating(
                circuit_id, value
            ),
        ),
        HitachiYutakiNumberEntityDescription(
            key="max_flow_temp_cooling_otc",
            translation_key="max_flow_temp_cooling_otc",
            description="Maximum cooling water temperature used in outdoor temperature compensation (OTC) calculations",
            native_min_value=0,
            native_max_value=80,
            native_step=1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
            condition=lambda coordinator: coordinator.has_circuit(
                circuit_id, CIRCUIT_MODE_COOLING
            ),
            get_fn=lambda api, circuit_id: api.get_circuit_max_flow_temp_cooling(
                circuit_id
            ),
            set_fn=lambda api, circuit_id, value: api.set_circuit_max_flow_temp_cooling(
                circuit_id, value
            ),
        ),
        HitachiYutakiNumberEntityDescription(
            key="heat_eco_offset",
            translation_key="heat_eco_offset",
            description="Temperature offset applied in ECO mode for heating",
            native_min_value=1,
            native_max_value=10,
            native_step=1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            condition=lambda coordinator: coordinator.has_circuit(
                circuit_id, CIRCUIT_MODE_HEATING
            ),
            get_fn=lambda api, circuit_id: float(value)
            if (value := api.get_circuit_heat_eco_offset(circuit_id)) is not None
            else None,
            set_fn=lambda api, circuit_id, value: api.set_circuit_heat_eco_offset(
                circuit_id, int(value)
            ),
        ),
        HitachiYutakiNumberEntityDescription(
            key="cool_eco_offset",
            translation_key="cool_eco_offset",
            description="Temperature offset applied in ECO mode for cooling",
            native_min_value=1,
            native_max_value=10,
            native_step=1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            condition=lambda coordinator: coordinator.has_circuit(
                circuit_id, CIRCUIT_MODE_COOLING
            ),
            get_fn=lambda api, circuit_id: float(value)
            if (value := api.get_circuit_cool_eco_offset(circuit_id)) is not None
            else None,
            set_fn=lambda api, circuit_id, value: api.set_circuit_cool_eco_offset(
                circuit_id, int(value)
            ),
        ),
    )
