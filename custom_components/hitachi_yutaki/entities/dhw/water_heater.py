"""DHW water heater builder."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.entity import DeviceInfo

from ...const import DEVICE_DHW, DOMAIN
from ..base.water_heater import (
    HitachiYutakiWaterHeater,
    HitachiYutakiWaterHeaterEntityDescription,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_dhw_water_heater(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> HitachiYutakiWaterHeater | None:
    """Build water heater entity for DHW."""
    if not coordinator.has_dhw():
        return None

    description = HitachiYutakiWaterHeaterEntityDescription(
        key="dhw",
        translation_key="dhw",
        description="Domestic hot water production",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{DEVICE_DHW}")},
    )

    return HitachiYutakiWaterHeater(
        coordinator=coordinator,
        description=description,
        device_info=device_info,
    )
