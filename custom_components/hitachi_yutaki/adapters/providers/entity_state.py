"""Entity state provider adapter for Home Assistant."""

from __future__ import annotations

from contextlib import suppress

from ...domain.ports.providers import StateProvider


class EntityStateProvider:
    """Adapter to provide entity states from Home Assistant."""

    def __init__(self, hass, config_entry) -> None:
        """Initialize the provider.

        Args:
            hass: Home Assistant instance
            config_entry: Configuration entry

        """
        self._hass = hass
        self._config_entry = config_entry

    def get_float_from_entity(self, config_key: str) -> float | None:
        """Get float value from a configured entity.

        Args:
            config_key: Configuration key for the entity

        Returns:
            Float value or None if unavailable

        """
        entity_id = self._config_entry.data.get(config_key)
        if not entity_id:
            return None

        state = self._hass.states.get(entity_id)
        if not state or state.state in (None, "unknown", "unavailable"):
            return None

        with suppress(ValueError):
            return float(state.state)
        return None


# Type alias for protocol compliance
StateProviderImpl: type[StateProvider] = EntityStateProvider
