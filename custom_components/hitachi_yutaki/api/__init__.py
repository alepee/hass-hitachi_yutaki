"""API for Hitachi heat pumps."""

from .base import HitachiApiClient
from .modbus import ModbusApiClient

GATEWAYS = {
    "modbus_atw_mbs_02": ModbusApiClient,
}

__all__ = ["HitachiApiClient", "GATEWAYS"]
