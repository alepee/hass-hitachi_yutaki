"""DHW button descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...const import DEVICE_DHW
from ..base.button import (
    HitachiYutakiButton,
    HitachiYutakiButtonEntityDescription,
    _create_buttons,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_dhw_buttons(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiButton]:
    """Build DHW button entities."""
    descriptions = _build_dhw_button_descriptions()
    return _create_buttons(coordinator, entry_id, descriptions, DEVICE_DHW, "dhw")


def _build_dhw_button_descriptions() -> tuple[
    HitachiYutakiButtonEntityDescription, ...
]:
    """Build DHW button descriptions."""
    return (
        HitachiYutakiButtonEntityDescription(
            key="antilegionella",
            translation_key="antilegionella",
            icon="mdi:biohazard",
            description="Start a high temperature anti-legionella treatment cycle. Once started, the cycle cannot be stopped.",
            entity_registry_enabled_default=True,
            action_fn=lambda coordinator: coordinator.api_client.start_dhw_antilegionella(),
        ),
    )
