"""Diagnostics support for Hitachi Yutaki."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import HitachiYutakiConfigEntry
from .api.config_providers import GATEWAY_CONFIG_PROVIDERS
from .const import CONF_MODBUS_HOST

TO_REDACT = {CONF_MODBUS_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HitachiYutakiConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    The ``gateway`` section comes from the gateway's config provider; on an
    HC-A(16/64)MB gateway it tells which unit the entry is bound to (#476).
    """
    coordinator = entry.runtime_data
    gateway_type = entry.data["gateway_type"]
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "gateway": {
            "gateway_type": gateway_type,
            "profile": entry.data.get("profile"),
            **GATEWAY_CONFIG_PROVIDERS[gateway_type]().diagnostics(entry.data),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "system_config": coordinator.system_config,
            "data": coordinator.data,
        },
    }
