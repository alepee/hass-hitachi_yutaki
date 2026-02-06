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
    CIRCUIT_IDS,
    CIRCUIT_MODES,
    DOMAIN,
)
from .domain.services.defrost_guard import DefrostGuard
from .profiles import HitachiHeatPumpProfile

_LOGGER = logging.getLogger(__name__)


class HitachiYutakiDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Hitachi heat pump data from the API."""

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
        self.entities: list[Any] = []
        self.defrost_guard = DefrostGuard()

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

            # Update defrost guard with fresh data
            water_inlet = data.get("water_inlet_temp")
            water_outlet = data.get("water_outlet_temp")
            delta_t = (
                (water_outlet - water_inlet)
                if water_inlet is not None and water_outlet is not None
                else None
            )
            self.defrost_guard.update(
                is_defrosting=self.api_client.is_defrosting,
                delta_t=delta_t,
            )

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

    def has_circuit(self, circuit_id: CIRCUIT_IDS, mode: CIRCUIT_MODES) -> bool:
        """Return True if circuit is configured in system_config."""
        return self.api_client.has_circuit(circuit_id, mode)

    def has_dhw(self) -> bool:
        """Return True if DHW is configured in system_config."""
        return self.api_client.has_dhw

    def has_pool(self) -> bool:
        """Return True if pool heating is configured in system_config."""
        return self.api_client.has_pool
