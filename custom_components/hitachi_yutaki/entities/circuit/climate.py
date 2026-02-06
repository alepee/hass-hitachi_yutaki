"""Circuit climate entity builder."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.entity import DeviceInfo

from ...const import (
    CIRCUIT_IDS,
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    DEVICE_TYPES,
    DOMAIN,
)
from ..base.climate import HitachiYutakiClimate, HitachiYutakiClimateEntityDescription

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_circuit_climate(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    circuit_id: CIRCUIT_IDS,
    device_type: DEVICE_TYPES,
) -> HitachiYutakiClimate | None:
    """Build climate entity for a circuit."""
    # Check if circuit is configured for heating or cooling
    if circuit_id == 1:
        if not (
            coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING)
            or coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING)
        ):
            return None
    elif circuit_id == 2:
        if not (
            coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING)
            or coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING)
        ):
            return None
    else:
        return None

    # Count total active circuits
    has_circuit1 = coordinator.has_circuit(
        CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING
    ) or coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING)
    has_circuit2 = coordinator.has_circuit(
        CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING
    ) or coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING)
    multi_circuit = has_circuit1 and has_circuit2

    description = HitachiYutakiClimateEntityDescription(
        key="climate",
        translation_key="climate",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{device_type}")},
    )

    return HitachiYutakiClimate(
        coordinator=coordinator,
        description=description,
        device_info=device_info,
        circuit_id=circuit_id,
        multi_circuit=multi_circuit,
    )
