# Adding Entities

This guide walks through the process of adding new entities to the integration --
whether extending an existing domain or creating a new one.

For background on why entities are organized the way they are, see the
[Architecture](../architecture.md) overview and the
[Entity Patterns](../reference/entity-patterns.md) reference.

## Key Concept

Entities are organized by **business domain** (gateway, circuit, dhw, pool, etc.),
not by Home Assistant entity type. A single domain folder can contain sensors,
binary sensors, switches, and numbers side by side. Platform files at the
component root (`sensor.py`, `binary_sensor.py`, ...) act as orchestrators that
call builder functions from each domain.

## Adding an Entity to an Existing Domain

This is the most common case. Suppose you need a new temperature sensor on the
control unit.

### 1. Identify the business domain

The sensor reads from the main heat pump unit, so it belongs in
`entities/control_unit/`. If it were related to a heating circuit, it would go in
`entities/circuit/`; for domestic hot water, `entities/dhw/`; and so on.

### 2. Open the entity type file

For a sensor, open `entities/control_unit/sensors.py`. For a binary sensor, open
`binary_sensors.py` in the same directory. The naming convention is always the
plural HA platform name.

### 3. Add a description to the builder function

Find `_build_control_unit_sensor_descriptions()` and add a new
`HitachiYutakiSensorEntityDescription` entry. Here is the existing file with a
new `discharge_temp` sensor appended:

```python
# In entities/control_unit/sensors.py

def _build_control_unit_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build control unit sensor descriptions."""
    return (
        # ... existing descriptions ...
        HitachiYutakiSensorEntityDescription(
            key="outdoor_temp",
            translation_key="outdoor_temp",
            description="Outdoor ambient temperature measurement",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            value_fn=lambda coordinator: coordinator.data.get("outdoor_temp"),
        ),
        # --- new entry ---
        HitachiYutakiSensorEntityDescription(
            key="discharge_temp",
            translation_key="discharge_temp",
            description="Compressor discharge temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            value_fn=lambda coordinator: coordinator.data.get("discharge_temp"),
        ),
    )
```

The `key` must match the Modbus register key used in `coordinator.data`. The
`translation_key` is looked up in translation files.

### 4. Add the translation key

Open `translations/en.json` and add an entry under the correct platform section:

```json
{
  "entity": {
    "sensor": {
      "discharge_temp": {
        "name": "Discharge Temperature"
      }
    }
  }
}
```

`en.json` is the source of truth. Other languages are managed via Weblate or
direct JSON edits.

### 5. Add a condition (if the entity is optional)

Some entities should only appear when the hardware supports them. Use the
`condition` field -- a lambda that receives the coordinator and returns a bool:

```python
HitachiYutakiBinarySensorEntityDescription(
    key="boiler",
    translation_key="boiler",
    description="Boiler running state",
    device_class=BinarySensorDeviceClass.RUNNING,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda coordinator: coordinator.api_client.is_boiler_active,
    condition=lambda c: c.profile.supports_boiler,
),
```

The `_create_*` factory functions evaluate the condition at setup time and skip
entities whose condition returns `False`.

### 6. Test

```bash
make test && make ha-run
```

Verify the entity appears in the HA developer tools under the expected device.

## Creating a New Domain

When entities do not logically belong to any existing domain, create a new one.

### 1. Create the directory

```
entities/
  new_domain/
    __init__.py
    sensors.py
```

### 2. Write the builder module

`entities/new_domain/sensors.py`:

```python
"""New domain sensor descriptions and builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass

from ...const import DEVICE_CONTROL_UNIT
from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_new_domain_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build new domain sensor entities."""
    descriptions = _build_new_domain_sensor_descriptions()
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT)


def _build_new_domain_sensor_descriptions() -> tuple[
    HitachiYutakiSensorEntityDescription, ...
]:
    """Build new domain sensor descriptions."""
    return (
        HitachiYutakiSensorEntityDescription(
            key="my_register_key",
            translation_key="my_register_key",
            description="Human-readable purpose of this sensor",
            device_class=SensorDeviceClass.TEMPERATURE,
            value_fn=lambda coordinator: coordinator.data.get("my_register_key"),
        ),
    )
```

### 3. Export from `__init__.py`

`entities/new_domain/__init__.py`:

```python
"""New domain entities."""

from .sensors import build_new_domain_sensors

__all__ = [
    "build_new_domain_sensors",
]
```

### 4. Register in the platform orchestrator

In `sensor.py`, import the builder and call it inside `async_setup_entry`:

```python
from .entities.new_domain import build_new_domain_sensors

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    # ... existing builders ...
    entities.extend(build_new_domain_sensors(coordinator, entry.entry_id))

    async_add_entities(entities)
```

### 5. Add translations

Add keys to `translations/en.json` as described in step 4 above.

## Common Pitfalls

**Dynamic device IDs instead of constants.** Always use the constants from
`const.py` (`DEVICE_CIRCUIT_1`, `DEVICE_CIRCUIT_2`, etc.). Building device IDs
with string interpolation like `f"circuit{circuit_id}"` produces `"circuit1"`
instead of the correct `"circuit_1"`, silently attaching entities to the wrong
device.

**Business logic in entity classes.** Entity descriptions should contain only
data access (`coordinator.data.get(...)`) and thin formatting. Any calculation,
accumulation, or decision logic belongs in `domain/services/`. The entity layer
must stay declarative.

**Importing HA modules in the domain layer.** The `domain/` package must never
import from `homeassistant.*`. If your new entity needs complex logic, implement
it as a domain service with a Protocol interface and inject an adapter.

**Missing conditions for optional features.** If a sensor only makes sense when
a specific hardware feature is present (DHW, pool, cooling mode, second
compressor), add a `condition` lambda. Without it, entities appear for users
whose hardware does not support the feature and show permanently unavailable.

**Reading CONTROL registers instead of STATUS registers.** The ATW-MBS-02
gateway exposes two register ranges. CONTROL registers reflect what was
*commanded*; STATUS registers reflect the *actual state*. Sensor entities must
always read from STATUS registers.

## Checklist

Use this checklist before opening a PR:

1. Entity is in the correct `entities/<domain>/` directory
2. Description added to the `_build_*_descriptions()` function
3. `key` matches the Modbus register key in `coordinator.data`
4. `translation_key` added to `translations/en.json` under the right platform
5. `condition` lambda present for optional/hardware-dependent features
6. Device type uses a constant from `const.py` (not a dynamic string)
7. No business logic in entity descriptions -- only data access
8. `value_fn` reads from STATUS registers, not CONTROL registers
9. Platform orchestrator updated if this is a new domain
10. `make test && make lint` pass
