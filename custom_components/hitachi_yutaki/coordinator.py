"""DataUpdateCoordinator for Hitachi Yutaki integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import HitachiApiClient
from .const import (
    CONF_POWER_SUPPLY,
    DEFAULT_POWER_SUPPLY,
    DOMAIN,
    MASK_CIRCUIT1_COOLING,
    MASK_CIRCUIT1_HEATING,
    MASK_CIRCUIT2_COOLING,
    MASK_CIRCUIT2_HEATING,
    MASK_DHW,
    MASK_POOL,
)
from .profiles import HitachiHeatPumpProfile

_LOGGER = logging.getLogger(__name__)


class HitachiYutakiDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Hitachi Yutaki heat pump."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api_client: HitachiApiClient,
        profile: HitachiHeatPumpProfile,
    ) -> None:
        """Initialize."""
        self.api_client = api_client
        self.profile = profile
        self.system_config = 0
        self.dev_mode = entry.data.get("dev_mode", False)
        self.power_supply = entry.data.get(CONF_POWER_SUPPLY, DEFAULT_POWER_SUPPLY)
        self.entities = []
        self.config_entry = entry

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=entry.data[CONF_SCAN_INTERVAL]),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Hitachi Yutaki."""
        try:
            if not self.api_client.connected:
                await self.api_client.connect()

            # Build full list of keys and fetch all data
            keys_to_read = (
                self.api_client.register_map.base_keys
                + self.profile.extra_register_keys
            )

            _LOGGER.debug("Reading %d keys from gateway", len(keys_to_read))
            await self.api_client.read_values(keys_to_read)

            data: dict[str, Any] = {"is_available": True}

            # Populate data from the client
            for key in keys_to_read:
                data[key] = await self.api_client.read_value(key)

            self.system_config = data.get("system_config", 0)

            # If we reach here, connection is successful, so delete any connection error issue
            ir.async_delete_issue(self.hass, DOMAIN, "connection_error")

            # Update timing sensors
            for entity in self.entities:
                if hasattr(entity, "async_update_timing"):
                    await entity.async_update_timing()

            return data

        except Exception as exc:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "connection_error",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="connection_error",
            )
            _LOGGER.warning("Error communicating with Hitachi Yutaki gateway: %s", exc)
            raise UpdateFailed("Failed to communicate with device") from exc

    async def async_write_register(self, register_key: str, value: int) -> None:
        """Write a value to a register."""
        try:
            await self.api_client.write_value(register_key, value)
            await self.async_request_refresh()
        except Exception as error:
            _LOGGER.error("Error writing to register %s: %s", register_key, error)
            raise UpdateFailed(f"Error writing to register {register_key}") from error

    def convert_temperature(self, value: int | None) -> int | None:
        """Convert a raw temperature value."""
        if value is None:
            return None
        if value == 0xFFFF:  # Special value for sensor error
            return None
        if value > 32767:  # Handle negative values (2's complement)
            value -= 65536
        return int(value)  # Temperature is already in °C

    def convert_water_flow(self, value: int | None) -> float | None:
        """Convert a raw water flow value to m³/h."""
        if value is None:
            return None
        return float(value) / 10.0  # Convert from tenths of m³/h to m³/h

    def convert_current(self, value: int | None) -> float | None:
        """Convert a raw current value to amperes."""
        if value is None:
            return None
        return float(value) / 10.0  # Current is already in A

    def convert_pressure(self, value: int | None) -> float | None:
        """Convert a raw pressure value from MPa to bar."""
        if value is None:
            return None
        # Convert from MPa to bar (1 MPa = 10 bar)
        return float(value) / 10.0  # Value is in MPa * 100, so divide by 10 to get bar

    def is_s80_model(self) -> bool:
        """Check if the unit is an S80 model."""
        return self.profile and self.profile.__class__.__name__ == "YutakiS80Profile"

    def has_heating_circuit1(self) -> bool:
        """Check if heating circuit 1 is configured."""
        return (
            self.profile
            and self.profile.supports_circuit1
            and (self.dev_mode or bool(self.system_config & MASK_CIRCUIT1_HEATING))
        )

    def has_heating_circuit2(self) -> bool:
        """Check if heating circuit 2 is configured."""
        return (
            self.profile
            and self.profile.supports_circuit2
            and (self.dev_mode or bool(self.system_config & MASK_CIRCUIT2_HEATING))
        )

    def has_cooling_circuit1(self) -> bool:
        """Check if cooling circuit 1 is configured."""
        return (
            self.profile
            and self.profile.supports_circuit1
            and (self.dev_mode or bool(self.system_config & MASK_CIRCUIT1_COOLING))
        )

    def has_cooling_circuit2(self) -> bool:
        """Check if cooling circuit 2 is configured."""
        return (
            self.profile
            and self.profile.supports_circuit2
            and (self.dev_mode or bool(self.system_config & MASK_CIRCUIT2_COOLING))
        )

    def has_dhw(self) -> bool:
        """Check if DHW is configured."""
        return (
            self.profile
            and self.profile.supports_dhw
            and (self.dev_mode or bool(self.system_config & MASK_DHW))
        )

    def has_pool(self) -> bool:
        """Check if pool is configured."""
        return (
            self.profile
            and self.profile.supports_pool
            and (self.dev_mode or bool(self.system_config & MASK_POOL))
        )
