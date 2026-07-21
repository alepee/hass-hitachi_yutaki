"""Compressor button descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import EntityCategory

from ...const import DEVICE_PRIMARY_COMPRESSOR
from ..base.button import (
    HitachiYutakiButton,
    HitachiYutakiButtonEntityDescription,
    _create_buttons,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_refrigerant_buttons(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiButton]:
    """Build the refrigerant detector reset button."""
    descriptions = _build_refrigerant_button_descriptions()
    return _create_buttons(
        coordinator, entry_id, descriptions, DEVICE_PRIMARY_COMPRESSOR
    )


def _build_refrigerant_button_descriptions() -> tuple[
    HitachiYutakiButtonEntityDescription, ...
]:
    """Build refrigerant detector button descriptions."""
    return (
        HitachiYutakiButtonEntityDescription(
            key="reset_refrigerant_baseline",
            translation_key="reset_refrigerant_baseline",
            icon="mdi:restart",
            entity_category=EntityCategory.CONFIG,
            description=(
                "Reset the refrigerant-charge detection baseline. Use after a "
                "refrigerant top-up or expansion-valve service so a new reference "
                "is learned from scratch."
            ),
            action_fn=lambda coordinator: (
                coordinator.async_reset_refrigerant_baseline()
            ),
        ),
    )
