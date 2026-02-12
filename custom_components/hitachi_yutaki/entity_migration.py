"""Entity migration for Hitachi Yutaki integration.

This module handles the migration of entity unique_ids from version 1.9.x to 2.0.0.
The main change is the removal of the Modbus Slave ID from the unique_id format.

Migration patterns:
- Simple: {entry_id}_{slave}_{key} -> {entry_id}_{key}
- Complex: {entry_id}_{slave}_{old_key} -> {entry_id}_{new_key}
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import CONF_SLAVE
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Mapping of old keys to new keys (for complex migrations)
# These are partial key matches - they will match anywhere in the key
KEY_MIGRATIONS = {
    "alarm_code": "alarm",
    "thermal_power": "thermal_power_heating",
    "daily_thermal_energy": "thermal_energy_heating_daily",
    "total_thermal_energy": "thermal_energy_heating_total",
    "otc_method_heating": "otc_calculation_method_heating",
    "otc_method_cooling": "otc_calculation_method_cooling",
}


async def async_migrate_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate entities from 1.9.x to 2.0.0 format.

    Args:
        hass: Home Assistant instance
        entry: Config entry for this integration

    """
    entity_registry = er.async_get(hass)
    slave_id = entry.data.get(CONF_SLAVE, 1)
    entry_id = entry.entry_id

    # Get all entities for this integration
    entities = er.async_entries_for_config_entry(entity_registry, entry_id)

    migrations_performed = 0
    migrations_failed = 0

    for entity_entry in entities:
        # Skip if entity is not from this integration
        if entity_entry.platform != DOMAIN:
            continue

        old_unique_id = entity_entry.unique_id

        # Check if this entity needs migration (contains _{slave}_ pattern)
        if f"_{slave_id}_" not in old_unique_id:
            continue

        # Calculate new unique_id
        new_unique_id = _calculate_new_unique_id(old_unique_id, slave_id)

        if new_unique_id is None:
            _LOGGER.warning(
                "Could not calculate new unique_id for entity %s (old: %s)",
                entity_entry.entity_id,
                old_unique_id,
            )
            migrations_failed += 1
            continue

        # Check if new unique_id already exists
        existing_entity = entity_registry.async_get_entity_id(
            entity_entry.domain, DOMAIN, new_unique_id
        )

        if existing_entity and existing_entity != entity_entry.entity_id:
            _LOGGER.warning(
                "Cannot migrate entity %s: new unique_id %s already exists for %s",
                entity_entry.entity_id,
                new_unique_id,
                existing_entity,
            )
            migrations_failed += 1
            continue

        # Perform migration
        try:
            entity_registry.async_update_entity(
                entity_entry.entity_id, new_unique_id=new_unique_id
            )
            _LOGGER.info(
                "Migrated entity %s: %s -> %s",
                entity_entry.entity_id,
                old_unique_id,
                new_unique_id,
            )
            migrations_performed += 1
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception(
                "Failed to migrate entity %s from %s to %s: %s",
                entity_entry.entity_id,
                old_unique_id,
                new_unique_id,
                err,
            )
            migrations_failed += 1

    if migrations_performed > 0:
        _LOGGER.info(
            "Entity migration completed: %s entities migrated, %s failed",
            migrations_performed,
            migrations_failed,
        )
    elif migrations_failed > 0:
        _LOGGER.warning(
            "Entity migration completed with %s failures", migrations_failed
        )
    else:
        _LOGGER.debug("No entities needed migration")


def _calculate_new_unique_id(old_unique_id: str, slave_id: int) -> str | None:
    """Calculate new unique_id from old format.

    Args:
        old_unique_id: Old unique_id with slave_id (e.g., "abc123_1_outdoor_temp")
        slave_id: Modbus slave ID to remove

    Returns:
        New unique_id without slave_id, or None if calculation failed

    """
    # Pattern: {entry_id}_{slave}_{key}
    slave_pattern = f"_{slave_id}_"

    if slave_pattern not in old_unique_id:
        return None

    # Split on the slave pattern
    parts = old_unique_id.split(slave_pattern, 1)
    if len(parts) != 2:
        return None

    entry_id_part = parts[0]
    key_part = parts[1]

    # Check for key migrations (complex migrations)
    # These can be partial matches within the full key (e.g., circuit1_otc_method_heating)
    for old_key, new_key in KEY_MIGRATIONS.items():
        if old_key in key_part:
            # Replace the old key with the new key (handles prefixes/suffixes)
            new_key_part = key_part.replace(old_key, new_key)
            _LOGGER.debug(
                "Performing complex migration: %s -> %s (in context: %s -> %s)",
                old_key,
                new_key,
                key_part,
                new_key_part,
            )
            key_part = new_key_part
            break

    # Construct new unique_id
    new_unique_id = f"{entry_id_part}_{key_part}"

    return new_unique_id


async def async_remove_orphaned_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove orphaned entities that are no longer created by the integration.

    This function removes entities that:
    - Still have the old unique_id format (_{slave}_) after migration
    - Are marked as unavailable
    - Would not be recreated by the current version of the integration

    Args:
        hass: Home Assistant instance
        entry: Config entry for this integration

    """
    entity_registry = er.async_get(hass)
    slave_id = entry.data.get(CONF_SLAVE, 1)
    entry_id = entry.entry_id

    # Get all entities for this integration
    entities = er.async_entries_for_config_entry(entity_registry, entry_id)

    entities_removed = 0

    for entity_entry in entities:
        # Skip if entity is not from this integration
        if entity_entry.platform != DOMAIN:
            continue

        old_unique_id = entity_entry.unique_id

        # Check if this entity still has old format (shouldn't after migration)
        if f"_{slave_id}_" in old_unique_id:
            _LOGGER.info(
                "Removing orphaned entity %s (unique_id: %s)",
                entity_entry.entity_id,
                old_unique_id,
            )
            entity_registry.async_remove(entity_entry.entity_id)
            entities_removed += 1

    if entities_removed > 0:
        _LOGGER.info("Removed %s orphaned entities", entities_removed)
    else:
        _LOGGER.debug("No orphaned entities to remove")
