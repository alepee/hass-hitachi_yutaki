"""API for Hitachi heat pumps."""

from dataclasses import dataclass

from .base import HitachiApiClient
from .modbus import ModbusApiClient


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
}

__all__ = ["HitachiApiClient", "GATEWAY_INFO"]
