"""The Hitachi Yutaki integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.translation import async_get_translations

from .const import (
    DOMAIN,
    GATEWAY_MODEL,
    MANUFACTURER,
    PLATFORMS,
    DEVICE_GATEWAY,
    DEVICE_CONTROL_UNIT,
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_SECONDARY_COMPRESSOR,
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_DHW,
    DEVICE_POOL,
    UNIT_MODEL_YUTAKI_S,
    UNIT_MODEL_YUTAKI_S_COMBI,
    UNIT_MODEL_S80,
    UNIT_MODEL_M,
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
    coordinator = HitachiYutakiDataCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Register devices
    device_registry = dr.async_get(hass)

    # Get translations for device names
    translations = await async_get_translations(
        hass,
        hass.config.language,
        "device",
        DOMAIN
    )

    def get_translated_name(device_key: str, fallback: str) -> str:
        """Get translated name for device with fallback."""
        return translations.get(f"device.{device_key}.name", fallback)

    # Add gateway device
    gateway_name = get_translated_name("gateway", DEVICE_GATEWAY.title())
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_GATEWAY}")},
        manufacturer=MANUFACTURER,
        model=GATEWAY_MODEL,
        name=gateway_name,
        configuration_url=f"http://{entry.data[CONF_HOST]}",
    )

    # Get unit model
    unit_model = coordinator.data.get("unit_model")
    model_name = MODEL_NAMES.get(unit_model, "Unknown Model")

    # Add main unit device
    control_unit_name = get_translated_name("control_unit", DEVICE_CONTROL_UNIT.replace("_", " ").title())
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
        manufacturer=MANUFACTURER,
        model=model_name,
        name=control_unit_name,
        via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_GATEWAY}"),
    )

    # Add primary compressor device
    primary_compressor_name = get_translated_name("primary_compressor", DEVICE_PRIMARY_COMPRESSOR.replace("_", " ").title())
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_PRIMARY_COMPRESSOR}")},
        manufacturer=MANUFACTURER,
        model=model_name,
        name=primary_compressor_name,
        via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
    )

    # Add secondary compressor device for S80 model
    if coordinator.is_s80_model():
        secondary_compressor_name = get_translated_name("secondary_compressor", DEVICE_SECONDARY_COMPRESSOR.replace("_", " ").title())
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_SECONDARY_COMPRESSOR}")},
            manufacturer=MANUFACTURER,
            model=model_name,
            name=secondary_compressor_name,
            via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
        )

    # Add Circuit 1 device if configured
    if coordinator.has_heating_circuit1() or coordinator.has_cooling_circuit1():
        circuit1_name = get_translated_name("circuit1", DEVICE_CIRCUIT_1.replace("_", " ").title())
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_1}")},
            manufacturer=MANUFACTURER,
            model=model_name,
            name=circuit1_name,
            via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
        )

    # Add Circuit 2 device if configured
    if coordinator.has_heating_circuit2() or coordinator.has_cooling_circuit2():
        circuit2_name = get_translated_name("circuit2", DEVICE_CIRCUIT_2.replace("_", " ").title())
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_2}")},
            manufacturer=MANUFACTURER,
            model=model_name,
            name=circuit2_name,
            via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
        )

    # Add DHW device if configured
    if coordinator.has_dhw():
        dhw_name = get_translated_name("dhw_heater", DEVICE_DHW.replace("_", " ").capitalize())
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DHW}")},
            manufacturer=MANUFACTURER,
            model=model_name,
            name=dhw_name,
            via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
        )

    # Add Pool device if configured
    if coordinator.has_pool():
        pool_name = get_translated_name("pool", DEVICE_POOL.replace("_", " ").title())
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_POOL}")},
            manufacturer=MANUFACTURER,
            model=model_name,
            name=pool_name,
            via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}"),
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]

        # Close Modbus connection
        if coordinator.modbus_client.connected:
            coordinator.modbus_client.close()

        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
