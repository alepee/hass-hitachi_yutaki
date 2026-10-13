"""Diagnostics support for Hitachi Yutaki."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import HitachiYutakiConfigEntry
from .const import (
    CONF_INDOOR_ADDRESS,
    CONF_MODBUS_HOST,
    CONF_OUTDOOR_CYCLE,
    CONF_UNIT_ID,
    DEFAULT_UNIT_ID,
)

TO_REDACT = {CONF_MODBUS_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HitachiYutakiConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    The ``unit`` section tells which physical machine an HC-A(16/64)MB entry is
    bound to: its ``(Ou, Iu)`` identity and the gateway slot it currently
    occupies (#476).
    """
    coordinator = entry.runtime_data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "unit": {
            "gateway_type": entry.data.get("gateway_type"),
            "profile": entry.data.get("profile"),
            "slot": entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
            "outdoor_cycle": entry.data.get(CONF_OUTDOOR_CYCLE),
            "indoor_address": entry.data.get(CONF_INDOOR_ADDRESS),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "system_config": coordinator.system_config,
            "data": coordinator.data,
        },
    }
