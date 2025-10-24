"""DHW switches for Hitachi Yutaki integration."""

from typing import Final

from .base import HitachiYutakiSwitchEntityDescription


def _build_dhw_switch_description() -> tuple[HitachiYutakiSwitchEntityDescription, ...]:
    """Build DHW switch descriptions."""
    return (
        HitachiYutakiSwitchEntityDescription(
            key="boost",
            name="Boost",
            icon="mdi:flash",
            condition=lambda c: c.has_dhw(),
            get_fn=lambda api, _: api.get_dhw_boost(),
            set_fn=lambda api, _, enabled: api.set_dhw_boost(enabled),
        ),
    )


# Legacy constant for backward compatibility
DHW_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="boost",
        name="Boost",
        icon="mdi:flash",
        condition=lambda c: c.has_dhw(),
        get_fn=lambda api, _: api.get_dhw_boost(),
        set_fn=lambda api, _, enabled: api.set_dhw_boost(enabled),
    ),
)
