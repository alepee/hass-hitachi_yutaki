"""DataUpdateCoordinator for Hitachi Yutaki integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pymodbus.exceptions import ModbusException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import HitachiApiClient
from .api.modbus import ModbusApiClient
from .api.modbus.registers.atw_mbs_02 import AtwMbs02RegisterMap
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
from .profiles import HitachiHeatPumpProfile, get_heat_pump_profile

_LOGGER = logging.getLogger(__name__)


class HitachiYutakiDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Hitachi Yutaki heat pump."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api_client: HitachiApiClient | None = None,
        profile: Any | None = None,
    ) -> None:
        """Initialize."""
        # Create default Modbus API client if none provided (backward-compatible)
        self.api_client: HitachiApiClient = api_client or ModbusApiClient(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            device_id=entry.data[CONF_DEVICE_ID],
            register_map=AtwMbs02RegisterMap(),
        )
        # Keep legacy attribute for unload logic compatibility
        self.modbus_client = getattr(self.api_client, "_client", None)
        self.device_id = entry.data[CONF_DEVICE_ID]
        self.model_key: str | None = None
        self.system_config = entry.data.get("system_config", 0)
        self.dev_mode = entry.data.get("dev_mode", False)
        self.power_supply = entry.data.get(CONF_POWER_SUPPLY, DEFAULT_POWER_SUPPLY)
        self.entities = []
        self.config_entry = entry
        self.profile: HitachiHeatPumpProfile | None = None

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
                await self.hass.async_add_executor_job(self.api_client.connect)

            data: dict[str, Any] = {"is_available": True}

            # Preflight check
            system_state = await self.hass.async_add_executor_job(
                lambda: self.api_client.read_value("system_state")
            )
            data["system_state"] = system_state

            # Determine model_key/profile once we have a connection
            if self.model_key is None:
                self.model_key = await self.hass.async_add_executor_job(
                    self.api_client.get_model_key
                )
                if self.model_key:
                    self.profile = get_heat_pump_profile(self.model_key)

            if system_state == 1:  # Desync
                _LOGGER.warning(
                    "The gateway is out of sync with the heat pump. Check the connection."
                )
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "desync_warning",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="desync_warning",
                )
                return data

            # If we are here, system_state is 0, so we can clear any previous issue
            ir.async_delete_issue(self.hass, DOMAIN, "desync_warning")

            if system_state == 2:  # Data init
                _LOGGER.info(
                    "Hitachi Yutaki is initializing, waiting for it to be ready..."
                )
                return data

            # Read all required registers (logical keys) using the map groupings
            # See ARCHITECTURE.md: Modbus register mapping is an infrastructure concern.
            # The coordinator consumes logical keys grouped by purpose.
            register_map = getattr(self.api_client, "register_map", None)
            register_keys = set()
            if register_map is not None:
                register_keys.update(register_map.config_keys())
                register_keys.update(register_map.control_keys())
                register_keys.update(register_map.sensor_keys())
                # Profile may request additional keys (e.g., S80 R134a) in a protocol-agnostic fashion
                if self.profile is not None:
                    register_keys.update(self.profile.extra_register_keys())
            else:
                # Fallback minimal set if no map available
                register_keys.update(
                    {"unit_model", "system_config", "system_status", "system_state"}
                )

            # Read registers one by one (we can batch later inside adapter)
            for register_name in register_keys:
                try:
                    value = await self.hass.async_add_executor_job(
                        lambda k=register_name: self.api_client.read_value(k)
                    )

                    # Update system configuration if reading system config
                    if register_name == "system_config":
                        self.system_config = value

                    # Store the value
                    data[register_name] = value

                except (ModbusException, Exception):
                    _LOGGER.warning(
                        "Error reading key %s",
                        register_name,
                        exc_info=True,
                    )
                    raise

            # Update timing sensors
            for entity in self.entities:
                if hasattr(entity, "async_update_timing"):
                    await entity.async_update_timing()

            return data

        except (ModbusException, ConnectionError, OSError, Exception) as exc:
            # Set is_available to False on any error
            _LOGGER.warning("Error communicating with Hitachi Yutaki gateway: %s", exc)
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "connection_error",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="connection_error",
            )
            raise UpdateFailed("Failed to communicate with device") from exc
        finally:
            # Clear connection error issue if connection succeeds on next update
            if self.last_update_success:
                ir.async_delete_issue(self.hass, DOMAIN, "connection_error")

    async def async_write_register(self, register_key: str, value: int) -> None:
        """Write a value to a register."""
        try:
            if not self.api_client.connected:
                await self.hass.async_add_executor_job(self.api_client.connect)

            register_map = getattr(self.api_client, "register_map", None)
            if register_map is not None and register_key not in set(
                register_map.control_keys()
            ):
                _LOGGER.error("Unknown register key: %s", register_key)
                return

            _LOGGER.debug(
                "Writing value %s to key %s",
                value,
                register_key,
            )

            await self.hass.async_add_executor_job(
                lambda k=register_key, v=value: self.api_client.write_value(k, v)
            )

            # Trigger an immediate update to refresh values
            await self.async_request_refresh()

        except (ModbusException, ConnectionError, OSError, Exception) as error:
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
        """Check if the unit is an S80 model (based on canonical model_key)."""
        return bool(self.profile and self.profile.model_key == "yutaki_s80")

    def has_heating_circuit1(self) -> bool:
        """Check if heating circuit 1 is available (profile + gateway + config)."""
        caps = getattr(self.api_client, "capabilities", None)
        gateway_ok = True
        if caps is not None:
            gateway_ok = (
                caps.circuits.get(1, None).heating if 1 in caps.circuits else False
            )
        profile_ok = True if self.profile is None else self.profile.supports_circuit1
        config_ok = self.dev_mode or bool(self.system_config & MASK_CIRCUIT1_HEATING)
        return profile_ok and config_ok and gateway_ok

    def has_heating_circuit2(self) -> bool:
        """Check if heating circuit 2 is available (profile + gateway + config)."""
        caps = getattr(self.api_client, "capabilities", None)
        gateway_ok = True
        if caps is not None:
            gateway_ok = (
                caps.circuits.get(2, None).heating if 2 in caps.circuits else False
            )
        profile_ok = True if self.profile is None else self.profile.supports_circuit2
        config_ok = self.dev_mode or bool(self.system_config & MASK_CIRCUIT2_HEATING)
        return profile_ok and config_ok and gateway_ok

    def has_cooling_circuit1(self) -> bool:
        """Check if cooling circuit 1 is available (profile + gateway + config)."""
        caps = getattr(self.api_client, "capabilities", None)
        gateway_ok = True
        if caps is not None:
            gateway_ok = (
                caps.circuits.get(1, None).cooling if 1 in caps.circuits else False
            )
        profile_ok = True if self.profile is None else self.profile.supports_circuit1
        config_ok = self.dev_mode or bool(self.system_config & MASK_CIRCUIT1_COOLING)
        return profile_ok and config_ok and gateway_ok

    def has_cooling_circuit2(self) -> bool:
        """Check if cooling circuit 2 is available (profile + gateway + config)."""
        caps = getattr(self.api_client, "capabilities", None)
        gateway_ok = True
        if caps is not None:
            gateway_ok = (
                caps.circuits.get(2, None).cooling if 2 in caps.circuits else False
            )
        profile_ok = True if self.profile is None else self.profile.supports_circuit2
        config_ok = self.dev_mode or bool(self.system_config & MASK_CIRCUIT2_COOLING)
        return profile_ok and config_ok and gateway_ok

    def has_dhw(self) -> bool:
        """Check if DHW is available (profile + gateway + config)."""
        caps = getattr(self.api_client, "capabilities", None)
        gateway_ok = True if caps is None else caps.dhw
        profile_ok = True if self.profile is None else self.profile.supports_dhw
        config_ok = self.dev_mode or bool(self.system_config & MASK_DHW)
        return profile_ok and config_ok and gateway_ok

    def has_pool(self) -> bool:
        """Check if pool is available (profile + gateway + config)."""
        caps = getattr(self.api_client, "capabilities", None)
        gateway_ok = True if caps is None else caps.pool
        profile_ok = True if self.profile is None else self.profile.supports_pool
        config_ok = self.dev_mode or bool(self.system_config & MASK_POOL)
        return profile_ok and config_ok and gateway_ok
