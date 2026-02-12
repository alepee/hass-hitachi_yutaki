"""Control unit select descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.climate import HVACMode

from ...const import (
    CIRCUIT_MODE_COOLING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    DEVICE_CONTROL_UNIT,
)
from ..base.select import (
    HitachiYutakiSelect,
    HitachiYutakiSelectEntityDescription,
    _create_selects,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_control_unit_selects(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSelect]:
    """Build control unit select entities."""
    descriptions = _build_control_unit_select_descriptions()
    return _create_selects(coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT)


def _build_control_unit_select_descriptions() -> tuple[
    HitachiYutakiSelectEntityDescription, ...
]:
    """Build control unit select descriptions."""
    return (
        HitachiYutakiSelectEntityDescription(
            key="operation_mode_heat",
            translation_key="operation_mode_heat",
            description="Operating mode of the heat pump (heating only unit)",
            options=["heat", "auto"],
            value_map={
                "heat": HVACMode.HEAT,
                "auto": HVACMode.AUTO,
            },
            condition=lambda coordinator: not (
                coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING)
                or coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING)
            ),
            get_fn=lambda api, _: api.get_unit_mode(),
            set_fn=lambda api, _, value: api.set_unit_mode(value),
        ),
        HitachiYutakiSelectEntityDescription(
            key="operation_mode_full",
            translation_key="operation_mode_full",
            description="Operating mode of the heat pump (heating and cooling unit)",
            options=["cool", "heat", "auto"],
            value_map={
                "cool": HVACMode.COOL,
                "heat": HVACMode.HEAT,
                "auto": HVACMode.AUTO,
            },
            condition=lambda coordinator: coordinator.has_circuit(
                CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING
            )
            or coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING),
            get_fn=lambda api, _: api.get_unit_mode(),
            set_fn=lambda api, _, value: api.set_unit_mode(value),
        ),
    )
