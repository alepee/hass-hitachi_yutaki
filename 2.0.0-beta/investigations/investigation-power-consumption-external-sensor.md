# Investigation: Use external sensor for power consumption

## Context

The `power_consumption` sensor currently relies exclusively on the ATW-MBS-02 gateway (Modbus register 1098). When configuring the integration, the user can already provide an external power sensor (`CONF_POWER_ENTITY`), but it is only used for COP calculation (via `ElectricalPowerCalculatorAdapter`), not for the `power_consumption` entity itself.

## Goal

If the user has configured an external power consumption sensor, use it as the source for the integration's `power_consumption` entity instead of the Modbus register. Additionally, expose a `source` attribute on the entity indicating where the data comes from:
- `"gateway"` — data from Modbus register 1098
- `"sensor.xxx"` — entity_id of the user-provided sensor

## Current State

### power_consumption sensor

Location: `entities/power/sensors.py`

```python
HitachiYutakiSensorEntityDescription(
    key="power_consumption",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    value_fn=lambda coordinator: coordinator.data.get("power_consumption"),
    entity_category=EntityCategory.DIAGNOSTIC,
)
```

- **device_class**: `ENERGY` (cumulative kWh)
- **state_class**: `TOTAL_INCREASING`
- **unit**: kWh
- **source**: Modbus register 1098 (raw integer, no conversion)

### CONF_POWER_ENTITY (existing config)

Location: `config_flow.py` (lines 82-87)

```python
vol.Optional(CONF_POWER_ENTITY): selector.EntitySelector(
    selector.EntitySelectorConfig(
        domain=["sensor"],
        device_class=["power"],
    ),
),
```

- Selects sensors with `device_class=power` — **instantaneous power in W**
- Stored in `config_entry.data["power_entity"]`
- Currently used only by `ElectricalPowerCalculatorAdapter` for COP calculation

### Unit mismatch

| Aspect | Integration sensor | CONF_POWER_ENTITY |
|--------|--------------------|-------------------|
| **device_class** | `ENERGY` | `power` |
| **unit** | kWh (cumulative) | W (instantaneous) |
| **state_class** | `TOTAL_INCREASING` | `MEASUREMENT` |

These are fundamentally different measurements. An instantaneous power sensor (W) cannot directly replace a cumulative energy sensor (kWh).

## Options

### Option A: New config option `CONF_ENERGY_ENTITY`

Add a dedicated config field for an external energy sensor (`device_class=energy`), independent from `CONF_POWER_ENTITY`.

**Pros:**
- Clean separation: power (W) for COP, energy (kWh) for consumption
- No risk of unit confusion
- Follows existing pattern (each external sensor has its own config key)

**Cons:**
- Adds a new config field to the already long power step
- User must configure both if they have both

**Implementation:**
1. Add `CONF_ENERGY_ENTITY = "energy_entity"` to `const.py`
2. Add entity selector with `device_class=["energy"]` to config flow and options flow
3. In `power_consumption` sensor, check for external energy entity first, fallback to Modbus
4. Add `source` attribute

### Option B: Reuse CONF_POWER_ENTITY

Use the existing `CONF_POWER_ENTITY` value directly for the `power_consumption` sensor.

**Pros:**
- No new config field
- Simpler UX

**Cons:**
- Unit mismatch: W vs kWh — values would be meaningless
- Would break COP calculation if the same entity is used for both purposes
- Violates HA conventions (device_class/unit must match)

### Option C: Widen CONF_POWER_ENTITY selector

Change the entity selector to accept both `power` and `energy` device classes, then adapt behavior based on what the user selects.

**Pros:**
- No new config field
- Flexible

**Cons:**
- Complex: must detect device_class at runtime and branch logic
- Same entity can't serve both COP (needs W) and consumption (needs kWh)
- Confusing for users

## Existing Pattern: Temperature fallback

The integration already implements this exact pattern for water temperatures (`entities/base/sensor.py:200-208`):

```python
def _get_temperature(self, entity_key: str, fallback_key: str) -> float | None:
    """Get temperature from a configured entity, falling back to coordinator data."""
    entity_id = self.coordinator.config_entry.data.get(entity_key)
    if entity_id:
        state = self.hass.states.get(entity_id)
        if state and state.state not in (None, "unknown", "unavailable"):
            with suppress(ValueError):
                return float(state.state)
    return self.coordinator.data.get(fallback_key)
```

This pattern (check external entity → fallback to coordinator) should be reused.

## Recommendation

**Option A** is the cleanest approach. It respects unit semantics, doesn't break existing COP logic, and follows the established pattern for external sensor configuration.

## Affected files (Option A)

| File | Change |
|------|--------|
| `const.py` | Add `CONF_ENERGY_ENTITY` constant |
| `config_flow.py` | Add energy entity selector to power step schema |
| `options_flow.py` (in config_flow.py) | Add energy entity selector to sensors step |
| `entities/power/sensors.py` | Modify builder to pass config_entry or add custom value_fn |
| `entities/base/sensor.py` | Add `source` attribute for `power_consumption` key in `extra_state_attributes` |
| `strings.json` / `translations/` | Add translation for new config field and source attribute |

## Open Questions

- Should the `source` attribute be on the entity description level (generic) or hardcoded for the `power_consumption` key only?
- Should the external energy entity's `state_class` and `unit_of_measurement` be validated at config time?
- If the external sensor becomes unavailable, should the entity fallback to the Modbus register or show `unavailable`?
