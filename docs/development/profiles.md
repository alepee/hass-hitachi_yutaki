# Heat Pump Profiles

## Overview

Profiles define the capabilities of each Hitachi heat pump model: supported circuits,
DHW temperature limits, cooling ability, secondary compressor, pool heating, and more.
They are auto-detected during the config flow based on Modbus register data, and they
live in `custom_components/hitachi_yutaki/profiles/`.

Every profile inherits from `HitachiHeatPumpProfile` and overrides only the properties
that differ from the defaults. The rest of the integration reads profile properties to
decide which entities to create, which temperature ranges to enforce, and which registers
to poll.

See also: [Architecture](../architecture.md) | [Modbus Registers](modbus-registers.md)

## How Detection Works

1. During the config flow, the integration reads Modbus registers from the ATW-MBS-02
   gateway. Register **1218** (`unit_model`) identifies the heat pump model and is
   decoded into a string key such as `"yutaki_s"`, `"yutaki_s80"`, etc.

2. Additional status registers provide context: `has_dhw`, `has_circuit1_heating`,
   `has_circuit1_cooling`, `has_circuit2_heating`, `has_circuit2_cooling`, and others.
   All decoded values are collected into a single `dict[str, Any]`.

3. Each profile class exposes a `detect(data)` static method that inspects this dict.
   Most profiles perform a simple key match:

   ```python
   @staticmethod
   def detect(data: dict[str, Any]) -> bool:
       return data.get("unit_model") == "yutaki_s"
   ```

   Some profiles use heuristic logic when the gateway reports an ambiguous model ID.
   For example, the ATW-MBS-02 reports both **Yutaki S Combi** and **Yutampo R32** as
   the same `unit_model` value. Yutampo R32 distinguishes itself by checking that DHW
   is present but no heating/cooling circuits are configured:

   ```python
   @staticmethod
   def detect(data: dict[str, Any]) -> bool:
       unit_model = data.get("unit_model")
       if unit_model == "yutampo_r32":
           return True
       return (
           unit_model == "yutaki_s_combi"
           and data.get("has_dhw") is True
           and not data.get("has_circuit1_heating")
           and not data.get("has_circuit1_cooling")
           and not data.get("has_circuit2_heating")
           and not data.get("has_circuit2_cooling")
       )
   ```

4. The first profile whose `detect()` returns `True` wins. If detection is ambiguous,
   the user is asked to select a model manually.

## Base Class

`HitachiHeatPumpProfile` (in `profiles/base.py`) is an abstract base class. Subclasses
**must** implement two abstract members:

| Member | Type | Purpose |
|--------|------|---------|
| `detect(data)` | `@staticmethod` | Return `True` when `data` matches this model |
| `name` | `@property` | Human-readable model name (e.g. `"Yutaki S80"`) |

All other properties have sensible defaults and are overridden only when needed:

### DHW capabilities

| Property | Default | Description |
|----------|---------|-------------|
| `supports_dhw` | `True` | Hardware support for Domestic Hot Water |
| `dhw_min_temp` | `30` | Minimum DHW setpoint (degrees C) |
| `dhw_max_temp` | `55` | Maximum DHW setpoint by heat pump alone |
| `antilegionella_min_temp` | `50` | Minimum anti-legionella temperature |
| `antilegionella_max_temp` | `80` | Maximum anti-legionella temperature |

### Circuit capabilities

| Property | Default | Description |
|----------|---------|-------------|
| `max_circuits` | `2` | Maximum heating/cooling circuits |
| `supports_circuit1` | derived | `True` when `max_circuits >= 1` |
| `supports_circuit2` | derived | `True` when `max_circuits >= 2` |
| `supports_cooling` | `True` | Cooling mode available |
| `max_water_outlet_temp` | `60` | Maximum water outlet temperature (degrees C) |

### Special features

| Property | Default | Description |
|----------|---------|-------------|
| `supports_high_temperature` | `False` | High-temp model (up to 80 degrees C outlet) |
| `supports_secondary_compressor` | `False` | Cascade compressor system (S80 only) |
| `supports_boiler` | `True` | Backup boiler support |
| `supports_pool` | `True` | Pool heating support |

### Extension points

| Property | Default | Description |
|----------|---------|-------------|
| `extra_register_keys` | `[]` | Additional Modbus registers to poll for this model |
| `entity_overrides` | `{}` | Dict of per-entity parameter overrides |

`extra_register_keys` lets a profile request registers that other models do not need.
The S80 profile uses this for secondary compressor sensors (discharge temp, suction
pressure, frequency, etc.).

`entity_overrides` lets a profile alter entity parameters without subclassing the entity
itself. The Yutampo R32 profile uses this to set a `boost_temp` on the water heater
entity for electric resistance heating:

```python
@property
def entity_overrides(self) -> dict:
    return {
        "water_heater": {
            "min_temp": 30,
            "max_temp": 55,
            "boost_temp": 75,
        }
    }
```

## Current Profiles

| Class | Name | Circuits | DHW max | Cooling | High temp | 2nd compressor | Pool | Boiler |
|-------|------|----------|---------|---------|-----------|----------------|------|--------|
| `YutakiSProfile` | Yutaki S | 2 | 55 | yes | no | no | yes | yes |
| `YutakiSCombiProfile` | Yutaki S Combi | 1 | 55 | yes | no | no | yes | yes |
| `YutakiS80Profile` | Yutaki S80 | 2 | 75 | no | yes | yes | yes | no |
| `YutakiMProfile` | Yutaki M | 2 | 55 | yes | no | no | yes | yes |
| `YutampoR32Profile` | Yutampo R32 | 0 | 55 | no | no | no | no | no |
| `YutakiScLiteProfile` | Yutaki SC Lite | 1 | 55 | yes | no | no | yes | yes |
| `YccProfile` | YCC | 2 | 55 | yes | no | no | yes | yes |

All profiles are registered in `profiles/__init__.py` via the `PROFILES` dict:

```python
PROFILES: dict[str, type[HitachiHeatPumpProfile]] = {
    "yutaki_s": YutakiSProfile,
    "yutaki_s_combi": YutakiSCombiProfile,
    "yutaki_s80": YutakiS80Profile,
    "yutaki_m": YutakiMProfile,
    "yutampo_r32": YutampoR32Profile,
    "yutaki_sc_lite": YutakiScLiteProfile,
    "ycc": YccProfile,
}
```

## Adding a New Profile

Follow these steps to add support for a new heat pump model.

### 1. Create the profile module

Create `profiles/your_model.py` inheriting from the base class. Override `detect()`,
`name`, and any capability properties that differ from the defaults.

```python
"""Profile for the Hitachi Your Model heat pump."""

from typing import Any

from .base import HitachiHeatPumpProfile


class YourModelProfile(HitachiHeatPumpProfile):
    """Profile for the Hitachi Your Model heat pump."""

    @staticmethod
    def detect(data: dict[str, Any]) -> bool:
        """Return True if the profile is detected."""
        return data.get("unit_model") == "your_model"

    @property
    def name(self) -> str:
        """Return the human-readable name of the heat pump model."""
        return "Your Model"

    # Override only what differs from the base defaults.
    # For example, if the model has no cooling:
    @property
    def supports_cooling(self) -> bool:
        return False
```

### 2. Register in the profile registry

Add the import and dict entry in `profiles/__init__.py`:

```python
from .your_model import YourModelProfile

PROFILES: dict[str, type[HitachiHeatPumpProfile]] = {
    # ...existing entries...
    "your_model": YourModelProfile,
}
```

### 3. Add model mapping in the register deserializer

If the new model uses a `unit_model` register value that is not yet mapped, add
the numeric-to-string mapping in the Modbus register decoder so that
`data["unit_model"]` resolves to your new key.

### 4. Add extra registers (if needed)

If the model exposes unique Modbus registers (like the S80's secondary compressor
data), override `extra_register_keys` to return the list of register key strings.
The coordinator will include them in its polling cycle.

### 5. Add entity overrides (if needed)

If the model requires different parameters on existing entities (temperature limits,
boost modes, etc.), override `entity_overrides` to return a dict keyed by entity type.

### 6. Test

Run `make test` and verify detection logic works with the new model data. Domain-layer
profile tests do not require Home Assistant mocks.
