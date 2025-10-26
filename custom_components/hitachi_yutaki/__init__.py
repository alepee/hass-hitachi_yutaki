"""The Hitachi Yutaki integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SLAVE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .api import GATEWAY_INFO
from .const import (
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_CONTROL_UNIT,
    DEVICE_DHW,
    DEVICE_GATEWAY,
    DEVICE_POOL,
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_SECONDARY_COMPRESSOR,
    DOMAIN,
    MANUFACTURER,
    PLATFORMS,
)
from .coordinator import HitachiYutakiDataCoordinator
from .profiles import PROFILES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hitachi Yutaki from a config entry."""
    _LOGGER.info("Setting up Hitachi Yutaki integration for %s", entry.data[CONF_NAME])

    # Get gateway and profile from config entry
    gateway_type = entry.data["gateway_type"]
    profile_key = entry.data["profile"]

    # Get gateway info (must exist)
    if gateway_type not in GATEWAY_INFO:
        raise ValueError(f"Unsupported gateway type: {gateway_type}")
    if profile_key not in PROFILES:
        raise ValueError(f"Unsupported profile: {profile_key}")

    gateway_info = GATEWAY_INFO[gateway_type]
    gateway_manufacturer = gateway_info.manufacturer
    gateway_model = gateway_info.model

    # Instantiate gateway client and profile
    api_client_class = gateway_info.client_class
    api_client = api_client_class(
        hass,
        name=entry.data[CONF_NAME],
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        slave=entry.data[CONF_SLAVE],
    )
    profile = PROFILES[profile_key]()

    coordinator = HitachiYutakiDataCoordinator(hass, entry, api_client, profile)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        _LOGGER.warning(
            "Initial connection to Hitachi Yutaki failed. "
            "The integration will retry in the background, and entities will be unavailable."
        )

    _LOGGER.debug("Data coordinator initialized")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Wait for the first refresh to succeed before setting up platforms
    await coordinator.async_config_entry_first_refresh()

    _LOGGER.info("Using Hitachi profile: %s", profile.name)

    # Register devices
    device_registry = dr.async_get(hass)
    _LOGGER.debug("Registering devices for unit model %s", profile.name)

    # Add gateway device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_GATEWAY}")},
        manufacturer=gateway_manufacturer,
        model=gateway_model,
        name=DEVICE_GATEWAY.title(),  # Fallback name
        translation_key="gateway",
        configuration_url=f"http://{entry.data[CONF_HOST]}",
    )

    # Add main unit device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
        manufacturer=MANUFACTURER,
        model=profile.name,
        name=DEVICE_CONTROL_UNIT.replace("_", " ").title(),  # Fallback name
        translation_key="control_unit",
        via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_GATEWAY}"),
    )

    # Add primary compressor device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_PRIMARY_COMPRESSOR}")},
        manufacturer=MANUFACTURER,
        model=profile.name,
        name=DEVICE_PRIMARY_COMPRESSOR.replace("_", " ").title(),  # Fallback name
        translation_key="primary_compressor",
        via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
    )

    # Add secondary compressor device for S80 model
    if profile.supports_secondary_compressor:
        _LOGGER.debug("Profile supports secondary compressor, registering device")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_SECONDARY_COMPRESSOR}")},
            manufacturer=MANUFACTURER,
            model=profile.name,
            name=DEVICE_SECONDARY_COMPRESSOR.replace("_", " ").title(),  # Fallback name
            translation_key="secondary_compressor",
            via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
        )

    # Add Circuit 1 device if configured
    if coordinator.has_circuit(
        CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING
    ) or coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING):
        _LOGGER.debug("Circuit 1 configured, registering device")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_1}")},
            manufacturer=MANUFACTURER,
            model=profile.name,
            name=DEVICE_CIRCUIT_1.replace("_", " ").title(),  # Fallback name
            translation_key="circuit1",
            via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
        )

    # Add Circuit 2 device if configured
    if coordinator.has_circuit(
        CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING
    ) or coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING):
        _LOGGER.debug("Circuit 2 configured, registering device")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_2}")},
            manufacturer=MANUFACTURER,
            model=profile.name,
            name=DEVICE_CIRCUIT_2.replace("_", " ").title(),  # Fallback name
            translation_key="circuit2",
            via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
        )

    # Add DHW device if configured
    if coordinator.has_dhw():
        _LOGGER.debug("DHW configured, registering device")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DHW}")},
            manufacturer=MANUFACTURER,
            model=profile.name,
            name=DEVICE_DHW.replace("_", " ").capitalize(),  # Fallback name
            translation_key="dhw",
            via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
        )

    # Add Pool device if configured
    if coordinator.has_pool():
        _LOGGER.debug("Pool configured, registering device")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_POOL}")},
            manufacturer=MANUFACTURER,
            model=profile.name,
            name=DEVICE_POOL.replace("_", " ").title(),  # Fallback name
            translation_key="pool",
            via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info(
        "Hitachi Yutaki integration setup completed for %s", entry.data[CONF_NAME]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Hitachi Yutaki integration for %s", entry.data[CONF_NAME])

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

        # Close API connection
        if coordinator.api_client.connected:
            _LOGGER.debug("Closing API connection")
            await coordinator.api_client.close()

        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Hitachi Yutaki integration unloaded successfully")

    return unload_ok
