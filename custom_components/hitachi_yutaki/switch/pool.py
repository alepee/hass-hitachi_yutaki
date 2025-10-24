"""Pool switches for Hitachi Yutaki integration."""

from typing import Final

from .base import HitachiYutakiSwitchEntityDescription


def _build_pool_switch_description() -> tuple[
    HitachiYutakiSwitchEntityDescription, ...
]:
    """Build pool switch descriptions."""
    return (
        HitachiYutakiSwitchEntityDescription(
            key="power",
            name="Power",
            icon="mdi:power",
            condition=lambda c: c.has_pool(),
            get_fn=lambda api, _: api.get_pool_power(),
            set_fn=lambda api, _, enabled: api.set_pool_power(enabled),
        ),
    )


# Legacy constant for backward compatibility
POOL_SWITCHES: Final[tuple[HitachiYutakiSwitchEntityDescription, ...]] = (
    HitachiYutakiSwitchEntityDescription(
        key="power",
        name="Power",
        icon="mdi:power",
        condition=lambda c: c.has_pool(),
        get_fn=lambda api, _: api.get_pool_power(),
        set_fn=lambda api, _, enabled: api.set_pool_power(enabled),
    ),
)
