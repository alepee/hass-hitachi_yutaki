"""Base sensor entity and description for Hitachi Yutaki."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import logging
from typing import Any, Literal

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ....const import (
    CONF_ENERGY_ENTITY,
    DEVICE_TYPES,
    DOMAIN,
)
from ....coordinator import HitachiYutakiDataCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class HitachiYutakiSensorEntityDescription(SensorEntityDescription):
    """Class describing Hitachi Yutaki sensor entities."""

    key: str
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    native_unit_of_measurement: str | None = None
    entity_category: EntityCategory | None = None
    icon: str | None = None
    entity_registry_enabled_default: bool = True
    translation_key: str | None = None
    description: str | None = None
    fallback_translation_key: str | None = None
    condition: Callable[[HitachiYutakiDataCoordinator], bool] | None = None
    value_fn: Callable[[HitachiYutakiDataCoordinator], StateType] | None = None
    sensor_class: Literal["cop", "thermal", "timing"] | None = None


def _create_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    descriptions: tuple[HitachiYutakiSensorEntityDescription, ...],
    device_type: DEVICE_TYPES,
) -> list[HitachiYutakiSensor]:
    """Create sensors for a specific device type.

    Dispatches to specialized subclasses based on ``sensor_class``.

    Args:
        coordinator: The data coordinator
        entry_id: The config entry ID
        descriptions: Sensor descriptions to create
        device_type: Device type identifier (e.g., DEVICE_GATEWAY)

    Returns:
        List of created sensor entities

    """
    # Local imports to avoid circular dependencies (subclasses import HitachiYutakiSensor)
    from .cop import HitachiYutakiCOPSensor  # noqa: PLC0415
    from .thermal import HitachiYutakiThermalSensor  # noqa: PLC0415
    from .timing import HitachiYutakiTimingSensor  # noqa: PLC0415

    _CLASS_MAP: dict[str, type[HitachiYutakiSensor]] = {
        "cop": HitachiYutakiCOPSensor,
        "thermal": HitachiYutakiThermalSensor,
        "timing": HitachiYutakiTimingSensor,
    }

    sensors: list[HitachiYutakiSensor] = []
    for description in descriptions:
        if description.condition is not None and not description.condition(coordinator):
            continue

        cls = _CLASS_MAP.get(description.sensor_class, HitachiYutakiSensor)

        sensors.append(
            cls(
                coordinator=coordinator,
                description=description,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, f"{entry_id}_{device_type}")},
                ),
            )
        )

    return sensors


class HitachiYutakiSensor(
    CoordinatorEntity[HitachiYutakiDataCoordinator], SensorEntity, RestoreEntity
):
    """Representation of a Hitachi Yutaki Sensor."""

    def __init__(
        self,
        coordinator: HitachiYutakiDataCoordinator,
        description: HitachiYutakiSensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

    def _get_temperature(self, entity_key: str, fallback_key: str) -> float | None:
        """Get temperature from a configured entity, falling back to coordinator data."""
        entity_id = self.coordinator.config_entry.data.get(entity_key)
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state and state.state not in (None, "unknown", "unavailable"):
                with suppress(ValueError):
                    return float(state.state)
        return self.coordinator.data.get(fallback_key)

    def _get_energy_value(self) -> StateType:
        """Get energy from configured external entity, or Modbus fallback."""
        entity_id = self.coordinator.config_entry.data.get(CONF_ENERGY_ENTITY)
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state and state.state not in (None, "unknown", "unavailable"):
                with suppress(ValueError):
                    return float(state.state)
            return None  # No fallback — external sensor configured but unavailable
        return self.coordinator.data.get("power_consumption")

    def _resolve_entity_id(self, platform_domain: str, key: str) -> str | None:
        """Return the entity_id registered for the provided (domain, unique_id)."""
        registry = er.async_get(self.hass)
        unique_id = f"{self.coordinator.config_entry.entry_id}_{key}"
        return registry.async_get_entity_id(platform_domain, DOMAIN, unique_id)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.key == "power_consumption":
            return self._get_energy_value()

        # For simple sensors, use value_fn if provided
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self.coordinator)

        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    def _get_alarm_attributes(self) -> dict[str, Any] | None:
        """Get attributes for alarm sensor."""
        if self.coordinator.data is None or not self.entity_description.value_fn:
            return None
        value = self.entity_description.value_fn(self.coordinator)
        if value is not None and value != 0:
            return {"code": value}
        return None

    def _get_operation_state_attributes(self) -> dict[str, Any] | None:
        """Get attributes for operation state sensor."""
        if self.coordinator.data is None:
            return None
        code = self.coordinator.data.get("operation_state_code")
        if code is not None:
            return {"code": code}
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        key = self.entity_description.key

        # Dispatch attributes based on sensor key
        if key == "alarm":
            return self._get_alarm_attributes()
        elif key == "operation_state":
            return self._get_operation_state_attributes()
        elif key == "power_consumption":
            entity_id = self.coordinator.config_entry.data.get(CONF_ENERGY_ENTITY)
            return {"source": entity_id if entity_id else "gateway"}

        return None
