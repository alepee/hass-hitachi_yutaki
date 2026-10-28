"""Circuit number descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.hitachi_yutaki.const import (
    CIRCUIT_IDS,
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    DEVICE_TYPES,
)
from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature

from ..base.number import (
    HitachiYutakiNumber,
    HitachiYutakiNumberEntityDescription,
    _create_numbers,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_circuit_numbers(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    circuit_id: CIRCUIT_IDS,
    device_type: DEVICE_TYPES,
) -> list[HitachiYutakiNumber]:
    """Build circuit number entities."""
    descriptions = _build_circuit_number_descriptions(circuit_id)
    return _create_numbers(
        coordinator, entry_id, descriptions, device_type, f"circuit{circuit_id}"
    )


def _build_circuit_number_descriptions(
    circuit_id: CIRCUIT_IDS,
) -> tuple[HitachiYutakiNumberEntityDescription, ...]:
    """Build circuit number descriptions."""
    return (
        # The room temperature Home Assistant reports to the heat pump, the
        # same register as the set_room_temperature action. Only meaningful
        # while the "External room sensor" switch is on, so
        # the entity is unavailable otherwise rather than silently ignored.
        HitachiYutakiNumberEntityDescription(
            key="room_temperature",
            translation_key="room_temperature",
            description="Room temperature reported to the heat pump by Home Assistant",
            native_min_value=0,
            native_max_value=50,
            native_step=0.5,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            mode=NumberMode.BOX,
            condition=lambda c: c.api_client.can_write(
                f"circuit{circuit_id}_current_temp"
            ),
            available_fn=lambda api, cid: api.external_room_sensor_enabled(cid),
            get_fn=lambda api, circuit_id: api.get_circuit_current_temperature(
                circuit_id
            ),
            set_fn=lambda api, circuit_id, value: api.set_circuit_room_temperature(
                circuit_id, value
            ),
        ),
        HitachiYutakiNumberEntityDescription(
            key="max_flow_temp_heating_otc",
            translation_key="max_flow_temp_heating_otc",
            description="Maximum heating water temperature used in outdoor temperature compensation (OTC) calculations",
            native_min_value=0,
            native_max_value=80,
            native_step=1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
            condition=lambda coordinator: coordinator.has_circuit(
                circuit_id, CIRCUIT_MODE_HEATING
            ),
            get_fn=lambda api, circuit_id: api.get_circuit_max_flow_temp_heating(
                circuit_id
            ),
            set_fn=lambda api, circuit_id, value: api.set_circuit_max_flow_temp_heating(
                circuit_id, value
            ),
        ),
        HitachiYutakiNumberEntityDescription(
            key="max_flow_temp_cooling_otc",
            translation_key="max_flow_temp_cooling_otc",
            description="Maximum cooling water temperature used in outdoor temperature compensation (OTC) calculations",
            native_min_value=0,
            native_max_value=80,
            native_step=1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
            condition=lambda coordinator: coordinator.has_circuit(
                circuit_id, CIRCUIT_MODE_COOLING
            ),
            get_fn=lambda api, circuit_id: api.get_circuit_max_flow_temp_cooling(
                circuit_id
            ),
            set_fn=lambda api, circuit_id, value: api.set_circuit_max_flow_temp_cooling(
                circuit_id, value
            ),
        ),
        HitachiYutakiNumberEntityDescription(
            key="heat_eco_offset",
            translation_key="heat_eco_offset",
            description="Temperature offset applied in ECO mode for heating",
            native_min_value=1,
            native_max_value=10,
            native_step=1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            condition=lambda c: (
                c.has_circuit(circuit_id, CIRCUIT_MODE_HEATING)
                and c.api_client.can_write(f"circuit{circuit_id}_heat_eco_offset")
            ),
            get_fn=lambda api, circuit_id: (
                float(value)
                if (value := api.get_circuit_heat_eco_offset(circuit_id)) is not None
                else None
            ),
            set_fn=lambda api, circuit_id, value: api.set_circuit_heat_eco_offset(
                circuit_id, int(value)
            ),
        ),
        HitachiYutakiNumberEntityDescription(
            key="cool_eco_offset",
            translation_key="cool_eco_offset",
            description="Temperature offset applied in ECO mode for cooling",
            native_min_value=1,
            native_max_value=10,
            native_step=1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            condition=lambda c: (
                c.has_circuit(circuit_id, CIRCUIT_MODE_COOLING)
                and c.api_client.can_write(f"circuit{circuit_id}_cool_eco_offset")
            ),
            get_fn=lambda api, circuit_id: (
                float(value)
                if (value := api.get_circuit_cool_eco_offset(circuit_id)) is not None
                else None
            ),
            set_fn=lambda api, circuit_id, value: api.set_circuit_cool_eco_offset(
                circuit_id, int(value)
            ),
        ),
    )
