"""Control unit switches for Hitachi Yutaki integration."""

from typing import Final

from .base import HitachiYutakiSwitchEntityDescription


def _build_control_unit_switch_description() -> tuple[
    HitachiYutakiSwitchEntityDescription, ...
]:
    """Build control unit switch descriptions."""
    return (
        HitachiYutakiSwitchEntityDescription(
            key="power",
            name="Power",
            icon="mdi:power",
            get_fn=lambda api, _: api.get_unit_power(),
            set_fn=lambda api, _, enabled: api.set_unit_power(enabled),
        ),
    )


# Legacy constant for backward compatibility
CONTROL_UNIT_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="power",
        name="Power",
        icon="mdi:power",
        get_fn=lambda api, _: api.get_unit_power(),
        set_fn=lambda api, _, enabled: api.set_unit_power(enabled),
    ),
)
