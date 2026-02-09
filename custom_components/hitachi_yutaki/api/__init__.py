"""API for Hitachi heat pumps."""

from __future__ import annotations

from dataclasses import dataclass

from ..const import DEFAULT_UNIT_ID
from .base import HitachiApiClient
from .modbus import ModbusApiClient
from .modbus.registers import HitachiRegisterMap
from .modbus.registers.hc_a_mb import HcAMbRegisterMap


@dataclass(frozen=True)
class GatewayInfo:
    """Gateway information."""

    manufacturer: str
    model: str
    client_class: type[HitachiApiClient]


GATEWAY_INFO = {
    "modbus_atw_mbs_02": GatewayInfo(
        manufacturer="Hitachi",
        model="ATW-MBS-02",
        client_class=ModbusApiClient,
    ),
    "modbus_hc_a_mb": GatewayInfo(
        manufacturer="Hitachi",
        model="HC-A(16/64)MB",
        client_class=ModbusApiClient,
    ),
}


def create_register_map(
    gateway_type: str, unit_id: int = DEFAULT_UNIT_ID
) -> HitachiRegisterMap | None:
    """Create the appropriate register map for the gateway type.

    Returns None for ATW-MBS-02 (uses built-in default).
    """
    if gateway_type == "modbus_hc_a_mb":
        return HcAMbRegisterMap(unit_id=unit_id)
    return None


__all__ = ["HitachiApiClient", "GATEWAY_INFO", "create_register_map"]
