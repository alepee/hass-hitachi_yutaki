# Entity Patterns

> For the overall integration structure, see [Architecture](../architecture.md).

## Overview

Entities are organized by **business domain** (circuit, DHW, compressor, etc.), not by
Home Assistant entity type (sensor, switch, climate, etc.). Each domain folder under
`entities/` contains all entity types relevant to that domain, built through a
three-layer pattern: description dataclasses, builder functions, and factory functions.

## Configuration Pattern

Every entity is declared as a description dataclass. The description holds all metadata
and behavior callbacks -- the entity class itself stays generic.

```python
@dataclass
class HitachiYutakiSensorEntityDescription(SensorEntityDescription):
    key: str
    translation_key: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    native_unit_of_measurement: str | None = None
    value_fn: Callable[[HitachiYutakiDataCoordinator], StateType] | None = None
    condition: Callable[[HitachiYutakiDataCoordinator], bool] | None = None
    sensor_class: Literal["cop", "thermal", "timing"] | None = None
```

Key fields across entity types:

| Field | Purpose |
|---|---|
| `key` | Unique identifier within the domain. Used in unique ID and register lookup. |
| `translation_key` | Maps to `strings.json` for localized names. |
| `value_fn` | Read callback (sensors, binary sensors). Receives the coordinator. |
| `get_fn` / `set_fn` | Read/write callbacks (switches, numbers, selects). Receive the API client and an optional circuit ID. |
| `condition` | Lambda that receives the coordinator; entity is skipped when it returns `False`. |
| `sensor_class` | Dispatches to a specialized sensor subclass (`cop`, `thermal`, `timing`). |

## Builder Pattern

Each domain defines `_build_<domain>_<type>_descriptions()` functions that return a
tuple of descriptions. Builders can accept parameters (e.g., `circuit_id`) to
construct context-specific descriptions:

```python
def _build_circuit_switch_descriptions(
    circuit_id: CIRCUIT_IDS,
) -> tuple[HitachiYutakiSwitchEntityDescription, ...]:
    return (
        HitachiYutakiSwitchEntityDescription(
            key="thermostat",
            name="Thermostat",
            condition=lambda c: c.data.get(
                f"circuit{circuit_id}_thermostat_available", False
            ),
            get_fn=lambda api, cid: api.get_circuit_thermostat(cid),
            set_fn=lambda api, cid, enabled: api.set_circuit_thermostat(cid, enabled),
        ),
    )
```

The public `build_<domain>_<type>()` function calls the builder then passes the
descriptions to the factory.

## Factory Pattern

Each base module exposes a `_create_<type>s()` factory that filters by condition and
instantiates entities:

```python
def _create_switches(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    descriptions: tuple[HitachiYutakiSwitchEntityDescription, ...],
    device_type: DEVICE_TYPES,
    register_prefix: str | None = None,
) -> list[HitachiYutakiSwitch]:
    entities = []
    for description in descriptions:
        if description.condition is not None and not description.condition(coordinator):
            continue  # Skip entities that don't meet their condition
        entities.append(HitachiYutakiSwitch(
            coordinator=coordinator, description=description,
            device_info=DeviceInfo(identifiers={(DOMAIN, f"{entry_id}_{device_type}")}),
            register_prefix=register_prefix,
        ))
    return entities
```

The sensor factory also dispatches to specialized subclasses via `sensor_class`.

## Conditional Creation

Conditions operate at two levels:

**Platform level** -- in the orchestrator (`sensor.py`, `switch.py`, etc.):

```python
if coordinator.has_dhw():
    entities.extend(build_dhw_sensors(coordinator, entry.entry_id))
if coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING):
    entities.extend(build_circuit_sensors(...))
```

**Description level** -- via the `condition` field on individual descriptions:

```python
condition=lambda c: c.data.get(f"circuit{circuit_id}_thermostat_available", False)  # hardware flag
condition=lambda c: c.has_dhw()   # DHW configured
condition=lambda c: c.has_pool()  # pool configured
```

The factory evaluates `condition` at setup time; entities whose condition returns
`False` are never instantiated.

## Unique ID Strategy

Format: `{entry_id}_{key}` or `{entry_id}_{prefix}_{key}` when a register prefix is
provided:

```python
entry_id = coordinator.config_entry.entry_id
if register_prefix:
    self._attr_unique_id = f"{entry_id}_{register_prefix}_{description.key}"
else:
    self._attr_unique_id = f"{entry_id}_{description.key}"
```

For circuit entities the prefix is `circuit1` or `circuit2`, producing IDs like
`abcdef_circuit1_thermostat`.

## Device Assignment

Entities are assigned to HA devices via `DEVICE_*` constants from `const.py`:

```python
DEVICE_GATEWAY = "gateway"
DEVICE_CONTROL_UNIT = "control_unit"
DEVICE_PRIMARY_COMPRESSOR = "outdoor_compressor"
DEVICE_SECONDARY_COMPRESSOR = "indoor_compressor"
DEVICE_CIRCUIT_1 = "circuit_1"
DEVICE_CIRCUIT_2 = "circuit_2"
DEVICE_DHW = "dhw"
DEVICE_POOL = "pool"
```

**Pitfall** -- always pass the constant, never build the string dynamically:

```python
# Correct: DEVICE_CIRCUIT_1 = "circuit_1"
build_circuit_switches(coordinator, entry_id, CIRCUIT_PRIMARY_ID, DEVICE_CIRCUIT_1)

# Wrong: f"circuit{CIRCUIT_PRIMARY_ID}" produces "circuit1" != "circuit_1"
build_circuit_switches(coordinator, entry_id, CIRCUIT_PRIMARY_ID, f"circuit{CIRCUIT_PRIMARY_ID}")
```

## Domain Folder Structure

```
entities/<domain>/
    __init__.py           # Re-exports public build_* functions
    sensors.py            # Sensor descriptions + builder
    switches.py           # Switch descriptions + builder (if needed)
    numbers.py            # Number descriptions + builder (if needed)
    selects.py            # Select descriptions + builder (if needed)
    climate.py            # Climate entity (circuit domain only)
    water_heater.py       # Water heater entity (DHW domain only)
```

A domain only includes the entity types it requires.

## Base Classes Reference

All base classes live under `entities/base/`.

| Base Class | Description Dataclass | Factory Function | File |
|---|---|---|---|
| `HitachiYutakiSensor` | `HitachiYutakiSensorEntityDescription` | `_create_sensors` | `base/sensor/base.py` |
| `HitachiYutakiBinarySensor` | `HitachiYutakiBinarySensorEntityDescription` | `_create_binary_sensors` | `base/binary_sensor.py` |
| `HitachiYutakiSwitch` | `HitachiYutakiSwitchEntityDescription` | `_create_switches` | `base/switch.py` |
| `HitachiYutakiNumber` | `HitachiYutakiNumberEntityDescription` | `_create_numbers` | `base/number.py` |
| `HitachiYutakiSelect` | `HitachiYutakiSelectEntityDescription` | `_create_selects` | `base/select.py` |
| `HitachiYutakiButton` | `HitachiYutakiButtonEntityDescription` | `_create_buttons` | `base/button.py` |
| `HitachiYutakiClimate` | (custom per domain) | (custom per domain) | `base/climate.py` |
| `HitachiYutakiWaterHeater` | (custom per domain) | (custom per domain) | `base/water_heater.py` |

Sensor has specialized subclasses dispatched by `sensor_class`. Climate and
water_heater do not use the generic description/factory pattern since they have
domain-specific logic.

## Quick Reference: Adding an Entity

1. Identify the business domain (`circuit/`, `dhw/`, `pool/`, etc.)
2. Open the matching file in `entities/<domain>/` (e.g., `sensors.py`, `switches.py`)
3. Add a new description to the `_build_<domain>_<type>_descriptions()` tuple
4. If the entity needs a condition, add a `condition` lambda
5. Verify the entity appears in HA and is attached to the correct device

For the full walkthrough, see [Adding Entities](../development/adding-entities.md).

## Quick Reference: Creating a New Domain

1. Create the folder `entities/<new_domain>/` with `__init__.py`
2. Add entity files (`sensors.py`, `switches.py`, etc.) with builder and description functions
3. Re-export public `build_*` functions from `__init__.py`
4. Import and call the builders from the platform orchestrators (`sensor.py`, `switch.py`, etc.)
5. Update [Architecture](../architecture.md) documentation
