# Investigation: Power Unit Conversion Heuristic

**Date**: 2026-01-29
**Status**: Open
**Issue**: #182
**Related Discussion**: https://github.com/alepee/hass-hitachi_yutaki/discussions/117#discussioncomment-15628772

## Problem

The current electrical power calculation uses a naive heuristic to convert W to kW:

```python
# domain/services/electrical.py:32-39
if data.measured_power is not None:
    # Simple heuristic to convert W to kW if necessary
    return (
        data.measured_power / 1000
        if data.measured_power > 50
        else data.measured_power
    )
```

This assumes:
- Values > 50 are in Watts
- Values <= 50 are in kW

**Issues**:
1. A heat pump in standby could consume < 50W, which would be incorrectly interpreted as kW
2. Home Assistant entities have a `unit_of_measurement` attribute that should be used instead

## Current Architecture

```
config_flow.py (UI config: power_entity)
    ↓
adapters/calculators/electrical.py (_get_float_from_entity)
    ↓ passes raw value without unit
domain/services/electrical.py (calculate_electrical_power)
    ↓ uses heuristic to guess unit
COP calculation
```

## Proposed Solution

Move unit conversion to the adapter layer (respects hexagonal architecture - domain stays HA-agnostic).

### Option A: Use Home Assistant's PowerConverter (Recommended)

Home Assistant provides a built-in `PowerConverter` class for deterministic unit conversion.

**Location**: `homeassistant.util.unit_conversion.PowerConverter`

**Supported units** (via `UnitOfPower` enum):
- `MILLIWATT`
- `WATT`
- `KILO_WATT`
- `MEGA_WATT`
- `GIGA_WATT`
- `TERA_WATT`
- `BTU_PER_HOUR`

Add `_get_power_in_kw()` method in `adapters/calculators/electrical.py`:

```python
from homeassistant.const import UnitOfPower
from homeassistant.util.unit_conversion import PowerConverter

def _get_power_in_kw(self) -> float | None:
    """Get power measurement normalized to kW using HA's PowerConverter."""
    entity_id = self._config_entry.data.get("power_entity")
    if not entity_id:
        return None

    state = self._hass.states.get(entity_id)
    if not state or state.state in (None, "unknown", "unavailable"):
        return None

    with suppress(ValueError):
        value = float(state.state)
        from_unit = state.attributes.get("unit_of_measurement")

        # Use HA's built-in converter for deterministic conversion
        return PowerConverter.convert(value, from_unit, UnitOfPower.KILO_WATT)

    return None
```

**Advantages**:
- Deterministic: uses actual `unit_of_measurement` attribute
- Maintained by HA core team
- Handles edge cases (BTU/h, mW, GW, etc.)
- Cached via `@lru_cache` for performance

Update `__call__` to use it:
```python
def __call__(self, current: float) -> float:
    return calculate_electrical_power(
        ElectricalPowerInput(
            current=current,
            measured_power=self._get_power_in_kw(),  # Already in kW
            voltage=self._get_float_from_entity("voltage_entity"),
            is_three_phase=self._is_three_phase,
        )
    )
```

Remove heuristic from domain layer:
```python
# domain/services/electrical.py
if data.measured_power is not None:
    return data.measured_power  # Already normalized to kW by adapter
```

### Option B: Pass unit to domain

Add `measured_power_unit` field to `ElectricalPowerInput` and handle conversion in domain.

**Rejected** because:
- Domain layer should not know about HA-specific unit strings
- Unit normalization is infrastructure concern, not business logic

## Files to Modify

1. `adapters/calculators/electrical.py` - Add `_get_power_in_kw()` method
2. `domain/services/electrical.py` - Remove heuristic, trust adapter normalization
3. Add tests for unit conversion

## Testing Considerations

- Test with W, kW, mW units
- Test with missing unit_of_measurement
- Test with entities in unknown/unavailable state
- Test standby power < 50W scenario

## Impact

- COP calculation accuracy improved for users with external power sensors
- No breaking changes (behavior improved, not changed fundamentally)
