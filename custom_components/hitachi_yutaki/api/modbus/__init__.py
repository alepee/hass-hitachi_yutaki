"""Modbus adapter scaffolding.

Provides a thin adapter class that will later implement HitachiApiClient.
Currently unused; kept as a placeholder to migrate coordinator Modbus calls.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pymodbus.exceptions import ModbusException

from .. import (
    CircuitCapabilities,
    GatewayCapabilities,
    HitachiApiClient,
    HitachiApiError,
)
from .client import ModbusClientShim
from .registers import HitachiRegisterMap
from .registers.atw_mbs_02 import AtwMbs02RegisterMap


class ModbusApiClient(HitachiApiClient):
    """Modbus TCP implementation of HitachiApiClient (placeholder)."""

    def __init__(
        self,
        host: str,
        port: int,
        device_id: int,
        register_map: HitachiRegisterMap | None = None,
    ):
        """Initialize the Modbus client and register map."""
        self._client = ModbusClientShim(host=host, port=port)
        self._device_id: int = device_id
        self._map: HitachiRegisterMap = register_map or AtwMbs02RegisterMap()

    def connect(self) -> bool:
        """Open the TCP connection to the Modbus gateway."""
        return self._client.connect()

    def close(self) -> None:
        """Close the TCP connection to the Modbus gateway."""
        self._client.close()

    @property
    def connected(self) -> bool:
        """Return True if the client is connected to the gateway."""
        return bool(self._client.connected)

    @property
    def register_map(self) -> HitachiRegisterMap:
        """Expose the underlying register map for grouped key access."""
        return self._map

    @property
    def capabilities(self) -> GatewayCapabilities:
        """Return supported features inferred from the available logical keys."""
        # Derive support purely from logical keys exposed by the map
        circuits = {
            1: CircuitCapabilities(
                heating=self._map.has_key("circuit1_power")
                or self._map.has_key("circuit1_target_temp"),
                cooling=self._map.has_key("circuit1_otc_calculation_method_cooling")
                or self._map.has_key("circuit1_max_flow_temp_cooling_otc"),
            ),
            2: CircuitCapabilities(
                heating=self._map.has_key("circuit2_power")
                or self._map.has_key("circuit2_target_temp"),
                cooling=self._map.has_key("circuit2_otc_calculation_method_cooling")
                or self._map.has_key("circuit2_max_flow_temp_cooling_otc"),
            ),
        }
        return GatewayCapabilities(
            dhw=self._map.has_key("dhw_power") or self._map.has_key("dhw_current_temp"),
            pool=self._map.has_key("pool_power")
            or self._map.has_key("pool_current_temp"),
            circuits=circuits,
        )

    def _key_to_address(self, key: str) -> int:
        try:
            return self._map.address_for_key(key)
        except KeyError as exc:
            raise HitachiApiError(f"Unknown key: {key}") from exc

    def read_value(self, key: str, *, context: Mapping[str, Any] | None = None) -> int:
        """Read a single holding register by logical key and return its value."""
        try:
            address = self._key_to_address(key)
            result = self._client.read_holding_registers(
                address=address, count=1, device_id=self._device_id
            )
            if result.isError():
                raise HitachiApiError(
                    f"Modbus error reading key {key} (addr {address})"
                )
            return int(result.registers[0])
        except (ModbusException, OSError) as exc:
            raise HitachiApiError(str(exc)) from exc

    def write_value(
        self, key: str, value: int, *, context: Mapping[str, Any] | None = None
    ) -> None:
        """Write a single holding register by logical key with the given value."""
        try:
            address = self._key_to_address(key)
            result = self._client.write_register(
                address=address, value=value, device_id=self._device_id
            )
            if result.isError():
                raise HitachiApiError(
                    f"Modbus error writing key {key} (addr {address})"
                )
        except (ModbusException, OSError) as exc:
            raise HitachiApiError(str(exc)) from exc

    def get_model_key(self) -> str | None:
        """Read the model via unit_model and translate to canonical key."""
        try:
            address = self._key_to_address("unit_model")
            result = self._client.read_holding_registers(
                address=address, count=1, device_id=self._device_id
            )
            if result.isError():
                return None
            model_num = int(result.registers[0])
            numeric_to_key = {
                0: "yutaki_s",
                1: "yutaki_s_combi",
                2: "yutaki_s80",
                3: "yutaki_m",
            }
            return numeric_to_key.get(model_num)
        except (ModbusException, OSError, HitachiApiError):
            return None
