"""The Hitachi Yutaki integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .api import GATEWAY_INFO, create_register_map
from .const import (
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    CONF_MODBUS_DEVICE_ID,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_UNIT_ID,
    DEFAULT_DEVICE_ID,
    DEFAULT_UNIT_ID,
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
from .entity_migration import async_migrate_entities
from .profiles import PROFILES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hitachi Yutaki from a config entry."""
    _LOGGER.info("Setting up Hitachi Yutaki integration for %s", entry.data[CONF_NAME])

    # Check for missing required configuration parameters
    missing_params = []
    if "gateway_type" not in entry.data:
        missing_params.append("gateway_type")
    if "profile" not in entry.data:
        missing_params.append("profile")

    if missing_params:
        # Create a repair issue to guide the user through reconfiguration
        async_create_issue(
            hass,
            DOMAIN,
            f"missing_config_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            issue_domain=DOMAIN,
            translation_key="missing_config",
        )

        # Return False to prevent setup until repair is completed
        # The user will need to go to the integration options to fix this
        return False

    # Migrate entities from 1.9.x to 2.0.0 format (remove slave_id from unique_id)
    # This must be done before creating new entities to avoid conflicts
    _LOGGER.debug("Checking for entity migrations")
    await async_migrate_entities(hass, entry)

    # Add unique_id if missing (for existing installations)
    if entry.unique_id is None:
        _LOGGER.info(
            "Config entry has no unique_id, attempting to add one based on hardware identifier"
        )

        # Create temporary API client for unique_id retrieval
        gateway_info = GATEWAY_INFO[entry.data["gateway_type"]]
        register_map = create_register_map(
            entry.data["gateway_type"],
            entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
        )
        temp_client = gateway_info.client_class(
            hass,
            name=entry.data[CONF_NAME],
            host=entry.data[CONF_MODBUS_HOST],
            port=entry.data[CONF_MODBUS_PORT],
            slave=entry.data[CONF_MODBUS_DEVICE_ID],
            register_map=register_map,
        )

        unique_id = None
        try:
            if await temp_client.connect():
                hw_id = await temp_client.async_get_unique_id()
                if hw_id:
                    unique_id = f"{DOMAIN}_{hw_id}"
                    _LOGGER.info(
                        "Added hardware-based unique_id to existing config entry: %s",
                        unique_id,
                    )
        except Exception as exc:
            _LOGGER.debug("Error retrieving hardware identifier: %s", exc)
        finally:
            if temp_client.connected:
                await temp_client.close()

        # Fallback to IP+slave if hardware ID unavailable
        if unique_id is None:
            unique_id = f"{entry.data[CONF_MODBUS_HOST]}_{entry.data[CONF_MODBUS_DEVICE_ID]}"
            _LOGGER.warning(
                "Could not retrieve hardware identifier, using IP-based unique_id: %s",
                unique_id,
            )

        hass.config_entries.async_update_entry(entry, unique_id=unique_id)

    # Get gateway and profile from config entry
    # At this point, these should exist (checked above)
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
    register_map = create_register_map(
        gateway_type, entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
    )
    api_client = api_client_class(
        hass,
        name=entry.data[CONF_NAME],
        host=entry.data[CONF_MODBUS_HOST],
        port=entry.data[CONF_MODBUS_PORT],
        slave=entry.data[CONF_MODBUS_DEVICE_ID],
        register_map=register_map,
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
        configuration_url=f"http://{entry.data[CONF_MODBUS_HOST]}",
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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entry to new version."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # Version 1 to 2: Add gateway_type and profile if missing
        new_data = {**config_entry.data}

        # Add gateway_type if missing (default to modbus_atw_mbs_02)
        if "gateway_type" not in new_data:
            new_data["gateway_type"] = "modbus_atw_mbs_02"

        # Add profile if missing (will trigger repair flow)
        if "profile" not in new_data:
            # Don't add a default profile - let the repair flow handle it
            pass

        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)
        _LOGGER.debug("Migration to version %s successful", config_entry.version)

    if config_entry.version == 2 and config_entry.minor_version < 2:
        # Version 2.1 to 2.2: Prefix Modbus connection keys with "modbus_"
        new_data = {**config_entry.data}

        # host → modbus_host
        if "host" in new_data:
            new_data["modbus_host"] = new_data.pop("host")
        # port → modbus_port
        if "port" in new_data:
            new_data["modbus_port"] = new_data.pop("port")
        # slave → modbus_device_id (direct from v2.1)
        if "slave" in new_data:
            new_data["modbus_device_id"] = new_data.pop("slave")
        elif "modbus_device_id" not in new_data:
            new_data["modbus_device_id"] = DEFAULT_DEVICE_ID

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, minor_version=2
        )
        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
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
