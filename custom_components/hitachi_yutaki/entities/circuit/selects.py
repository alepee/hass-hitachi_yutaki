"""Circuit select descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import EntityCategory

from ...const import (
    CIRCUIT_IDS,
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    DEVICE_TYPES,
    OTCCalculationMethod,
)
from ..base.select import (
    HitachiYutakiSelect,
    HitachiYutakiSelectEntityDescription,
    _create_selects,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_circuit_selects(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    circuit_id: CIRCUIT_IDS,
    device_type: DEVICE_TYPES,
) -> list[HitachiYutakiSelect]:
    """Build circuit select entities."""
    descriptions = _build_circuit_select_descriptions(circuit_id)
    return _create_selects(
        coordinator, entry_id, descriptions, device_type, f"circuit{circuit_id}"
    )


def _build_circuit_select_descriptions(
    circuit_id: CIRCUIT_IDS,
) -> tuple[HitachiYutakiSelectEntityDescription, ...]:
    """Build circuit select descriptions."""
    return (
        HitachiYutakiSelectEntityDescription(
            key="otc_calculation_method_heating",
            translation_key="otc_calculation_method_heating",
            description="Method used to calculate the heating water temperature based on outdoor temperature (OTC - Outdoor Temperature Compensation)",
            options=["disabled", "points", "gradient", "fix"],
            value_map={
                "disabled": OTCCalculationMethod.DISABLED,
                "points": OTCCalculationMethod.POINTS,
                "gradient": OTCCalculationMethod.GRADIENT,
                "fix": OTCCalculationMethod.FIX,
            },
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
            condition=lambda coordinator: coordinator.has_circuit(
                circuit_id, CIRCUIT_MODE_HEATING
            ),
            get_fn=lambda api, circuit_id: api.get_circuit_otc_method_heating(
                circuit_id
            ),
            set_fn=lambda api, circuit_id, value: api.set_circuit_otc_method_heating(
                circuit_id, value
            ),
        ),
        HitachiYutakiSelectEntityDescription(
            key="otc_calculation_method_cooling",
            translation_key="otc_calculation_method_cooling",
            description="Method used to calculate the cooling water temperature based on outdoor temperature (OTC - Outdoor Temperature Compensation)",
            options=["disabled", "points", "fix"],
            value_map={
                "disabled": OTCCalculationMethod.DISABLED,
                "points": OTCCalculationMethod.POINTS,
                "fix": OTCCalculationMethod.FIX,
            },
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
            condition=lambda coordinator: coordinator.has_circuit(
                circuit_id, CIRCUIT_MODE_COOLING
            ),
            get_fn=lambda api, circuit_id: api.get_circuit_otc_method_cooling(
                circuit_id
            ),
            set_fn=lambda api, circuit_id, value: api.set_circuit_otc_method_cooling(
                circuit_id, value
            ),
        ),
    )
