# Energy Cost Estimation — Design Spec

## Goal

Centralize electrical energy resolution in the `DerivedMetricsAdapter` and use it to:

1. Provide cumulative electrical energy consumption (kWh) — refactoring the existing `power_consumption` sensor to read from the adapter instead of having its own cascade logic in the base sensor entity.
2. Allow users to provide an electricity price sensor to estimate cumulative energy cost.

## Constraints

- The cost sensor is only created when a price entity is configured — no default, no fallback.
- The integration does not validate the price sensor's unit. The config flow description states the expected format (`{currency}/kWh`), and the user is responsible for providing a compatible sensor.
- Currency is read from `hass.config.currency`.

---

## 1. Configuration

### New constant

`CONF_ELECTRICITY_PRICE_ENTITY = "electricity_price_entity"` in `const.py`.

### Config flow — options step `sensors`

Add `electricity_price_entity` to `POWER_SCHEMA`:

```python
vol.Optional(CONF_ELECTRICITY_PRICE_ENTITY): selector.EntitySelector(
    selector.EntitySelectorConfig(
        domain=["sensor", "number", "input_number"],
    ),
),
```

Stored in `entry.data` alongside `voltage_entity`, `power_entity`, etc.

### Repair flow — `EnergyCostRepairFlow`

For existing users upgrading to this version:

- Issue created at setup if `electricity_price_entity` is not configured.
- `is_fixable: True`, `is_persistent: True`, severity `WARNING`.
- The repair flow presents a single-field form (`electricity_price_entity` selector).
- On confirm: updates `entry.data`, deletes the issue, reloads the integration.
- If ignored: nothing breaks, the cost sensor is not created.

### Translations

New keys in `en.json`:
- Config flow: label and description for the `electricity_price_entity` field (description mentions `{currency}/kWh`).
- Repair flow: title and description explaining the new feature.

---

## 2. Calculation — DerivedMetricsAdapter

### Energy source resolution (unified helper)

Extract a `_resolve_electrical_energy()` method in the adapter that returns the current energy value (kWh) following this cascade:

1. **`energy_entity`** (external counter configured by user) — most accurate
2. **`power_consumption`** (Modbus built-in counter, if available) — accurate
3. **`electrical_power`** (calculated from current × voltage) — fallback, requires time integration

This helper replaces the existing `_get_energy_value()` in the base sensor entity, which currently implements the same cascade. The adapter:

- Tracks the previous energy reading to compute `delta_kWh` each cycle.
- Accumulates electrical energy (kWh) and injects into `data["power_consumption"]` — replaces the current sensor's custom cascade logic.
- The existing `power_consumption` sensor is refactored to read from `data` via `value_fn`, like all other derived sensors.

### Cost accumulation

At each poll cycle:

1. Read price from `electricity_price_entity` via `hass.states.get()`.
2. Compute `delta_kWh` from the energy source helper (counter difference for sources 1-2, power × dt for source 3).
3. **Gap detection**: if `dt > 2 × poll_interval`, skip accumulation for this cycle (price may have changed during the gap — unreliable data).
4. Accumulate: `electricity_cost += delta_kWh × price`.
5. Inject `data["electricity_cost"] = electricity_cost`.

### Edge cases

- **Price unavailable** (`unknown`, `unavailable`, `None`): no accumulation, counter stalls.
- **Energy unavailable**: no accumulation, counter stalls.
- **HA restart**: total restored from HA state restore (same pattern as `thermal_energy_*_total`). First cycle after restart skipped due to gap detection.
- **Energy source change** (user adds/removes `energy_entity` mid-operation): counter continues accumulating, only the delta source changes.

---

## 3. Sensors

### `power_consumption` — Cumulative electrical energy (refactored internals)

Existing sensor — **key and entity_id unchanged** to preserve user history.

The refactor replaces the custom `_get_energy_value()` logic in the base sensor entity. The adapter now resolves the energy source and injects the value into `data["power_consumption"]`. The sensor becomes a simple `value_fn` reader like all other derived sensors.

Extra attributes:

| Attribute | Description |
|---|---|
| `energy_source` | `"external"`, `"gateway"`, or `"calculated"` — active source in the cascade |

### `electricity_cost` — Cumulative energy cost (new)

| Property | Value |
|---|---|
| `device_class` | `SensorDeviceClass.MONETARY` |
| `state_class` | `SensorStateClass.TOTAL_INCREASING` |
| `native_unit_of_measurement` | `hass.config.currency` |
| `value_fn` | `lambda c: c.data.get("electricity_cost")` |
| `condition` | price entity is configured |
| Device | `DEVICE_CONTROL_UNIT` |

Extra attributes:

| Attribute | Description |
|---|---|
| `price_entity` | Entity ID of the configured price sensor |
| `current_price` | Price value read at last cycle |
| `energy_source` | `"external"`, `"gateway"`, or `"calculated"` — active source in the cascade |

### State restoration

`electricity_cost` restored from HA state restore on restart, same pattern as `thermal_energy_*_total`. `power_consumption` keeps its existing restoration logic.

---

## 4. Files impacted

| File | Change |
|---|---|
| `const.py` | Add `CONF_ELECTRICITY_PRICE_ENTITY` |
| `config_flow.py` | Add field to `POWER_SCHEMA` and options flow defaults |
| `repairs.py` | Add `EnergyCostRepairFlow` |
| `__init__.py` | Create repair issue at setup if not configured |
| `adapters/derived_metrics.py` | Add `_resolve_electrical_energy()`, cost accumulation logic, state restore |
| `entities/base/sensor/base.py` | Remove `_get_energy_value()`, read from `data` dict instead |
| `entities/thermal/sensors.py` or `entities/performance/sensors.py` | Add `energy_cost` sensor description |
| `translations/en.json` | Config flow + repair translations |

---

## 5. Out of scope

- Price unit validation or conversion (user responsibility).
- Daily/monthly cost breakdown (user can use `utility_meter`).
- Cost forecasting or optimization recommendations.
