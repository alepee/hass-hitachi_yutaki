"""The Hitachi Yutaki integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_CONTROL_UNIT,
    DEVICE_DHW,
    DEVICE_GATEWAY,
    DEVICE_POOL,
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_SECONDARY_COMPRESSOR,
    DOMAIN,
    GATEWAY_MODEL,
    MANUFACTURER,
    PLATFORMS,
    UNIT_MODEL_M,
    UNIT_MODEL_S80,
    UNIT_MODEL_YUTAKI_S,
    UNIT_MODEL_YUTAKI_S_COMBI,
)
from .coordinator import HitachiYutakiDataCoordinator

_LOGGER = logging.getLogger(__name__)

MODEL_NAMES = {
    UNIT_MODEL_YUTAKI_S: "Yutaki S",
    UNIT_MODEL_YUTAKI_S_COMBI: "Yutaki S Combi",
    UNIT_MODEL_S80: "Yutaki S80",
    UNIT_MODEL_M: "Yutaki M",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hitachi Yutaki from a config entry."""
    _LOGGER.info("Setting up Hitachi Yutaki integration for %s", entry.data[CONF_NAME])

    coordinator = HitachiYutakiDataCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        _LOGGER.warning(
            "Initial connection to Hitachi Yutaki failed. "
            "The integration will retry in the background, and entities will be unavailable."
        )

    _LOGGER.debug("Data coordinator initialized")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Determine model name from selected profile (string identifier)
    model_name = coordinator.profile.name if coordinator.profile else "Unknown Model"
    _LOGGER.info("Detected Hitachi unit model: %s", model_name)

    # Register devices
    device_registry = dr.async_get(hass)
    _LOGGER.debug("Registering devices for unit model %s", model_name)

    # Add gateway device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_GATEWAY}")},
        manufacturer=MANUFACTURER,
        model=GATEWAY_MODEL,
        name=DEVICE_GATEWAY.title(),  # Fallback name
        translation_key="gateway",
        configuration_url=f"http://{entry.data[CONF_HOST]}",
    )

    # Add main unit device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
        manufacturer=MANUFACTURER,
        model=model_name,
        name=DEVICE_CONTROL_UNIT.replace("_", " ").title(),  # Fallback name
        translation_key="control_unit",
        via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_GATEWAY}"),
    )

    # Add primary compressor device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_PRIMARY_COMPRESSOR}")},
        manufacturer=MANUFACTURER,
        model=model_name,
        name=DEVICE_PRIMARY_COMPRESSOR.replace("_", " ").title(),  # Fallback name
        translation_key="primary_compressor",
        via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
    )

    # Add secondary compressor device for S80 model
    if coordinator.is_s80_model():
        _LOGGER.debug("S80 model detected, registering secondary compressor")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_SECONDARY_COMPRESSOR}")},
            manufacturer=MANUFACTURER,
            model=model_name,
            name=DEVICE_SECONDARY_COMPRESSOR.replace("_", " ").title(),  # Fallback name
            translation_key="secondary_compressor",
            via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
        )

    # Add Circuit 1 device if configured
    if coordinator.has_heating_circuit1() or coordinator.has_cooling_circuit1():
        _LOGGER.debug("Circuit 1 configured, registering device")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_1}")},
            manufacturer=MANUFACTURER,
            model=model_name,
            name=DEVICE_CIRCUIT_1.replace("_", " ").title(),  # Fallback name
            translation_key="circuit1",
            via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
        )

    # Add Circuit 2 device if configured
    if coordinator.has_heating_circuit2() or coordinator.has_cooling_circuit2():
        _LOGGER.debug("Circuit 2 configured, registering device")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_2}")},
            manufacturer=MANUFACTURER,
            model=model_name,
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
            model=model_name,
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
            model=model_name,
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

        # Close Modbus connection
        if coordinator.modbus_client.connected:
            _LOGGER.debug("Closing Modbus connection")
            coordinator.modbus_client.close()

        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Hitachi Yutaki integration unloaded successfully")

    return unload_ok
