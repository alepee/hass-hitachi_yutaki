"""API for Hitachi heat pumps."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from ..const import (
    CONF_MODBUS_DEVICE_ID,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_OUTDOOR_CYCLE,
    CONF_UNIT_ID,
    DEFAULT_UNIT_ID,
)
from .base import HitachiApiClient
from .modbus import ModbusApiClient
from .modbus.hc_a_mb import HcAMbApiClient
from .modbus.registers import GATEWAY_VARIANTS, HitachiRegisterMap
from .modbus.registers.hc_a_mb import HcAMbRegisterMap


@dataclass(frozen=True)
class GatewayInfo:
    """Gateway information."""

    manufacturer: str
    model: str
    client_class: type[HitachiApiClient]


DEFAULT_GATEWAY_TYPE = "modbus_atw_mbs_02"

GATEWAY_INFO = {
    "modbus_atw_mbs_02": GatewayInfo(
        manufacturer="Hitachi",
        model="ATW-MBS-02",
        client_class=ModbusApiClient,
    ),
    "modbus_hc_a_mb": GatewayInfo(
        manufacturer="Hitachi",
        model="HC-A(16/64)MB",
        client_class=HcAMbApiClient,
    ),
}


def create_register_map(
    gateway_type: str,
    unit_id: int = DEFAULT_UNIT_ID,
    gateway_variant: str | None = None,
    outdoor_cycle: int | None = None,
) -> HitachiRegisterMap | None:
    """Create the appropriate register map for the gateway type and variant.

    The ``outdoor_cycle`` argument only applies to the HC-A(16/64)MB gateway,
    where the outdoor register block is keyed on the outdoor refrigerant cycle
    (#353). It is ignored for other gateways.

    Returns None for ATW-MBS-02 gen2 (uses built-in default).
    """
    if gateway_type == "modbus_hc_a_mb":
        return HcAMbRegisterMap(unit_id=unit_id, outdoor_cycle=outdoor_cycle)

    # Check for variant-specific register map
    variants = GATEWAY_VARIANTS.get(gateway_type)
    if variants and gateway_variant and gateway_variant in variants:
        return variants[gateway_variant]()

    return None


def create_api_client(
    hass: HomeAssistant, config: Mapping[str, Any]
) -> HitachiApiClient:
    """Create the gateway client described by config entry (or flow) data.

    Callers stay gateway-agnostic: the client class and its register map are
    chosen from ``gateway_type`` and the gateway-specific keys stored with it.
    """
    gateway_type = config["gateway_type"]
    return GATEWAY_INFO[gateway_type].client_class(
        hass,
        name=config[CONF_NAME],
        host=config[CONF_MODBUS_HOST],
        port=config[CONF_MODBUS_PORT],
        slave=config[CONF_MODBUS_DEVICE_ID],
        register_map=create_register_map(
            gateway_type,
            config.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
            gateway_variant=config.get("gateway_variant"),
            outdoor_cycle=config.get(CONF_OUTDOOR_CYCLE),
        ),
    )


__all__ = [
    "DEFAULT_GATEWAY_TYPE",
    "GATEWAY_INFO",
    "HitachiApiClient",
    "create_api_client",
    "create_register_map",
]
