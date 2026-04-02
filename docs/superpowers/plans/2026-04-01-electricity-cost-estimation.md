# Electricity Cost Estimation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional electricity price sensor input, centralize energy resolution in `DerivedMetricsAdapter`, and expose a `total_increasing` electricity cost sensor.

**Architecture:** The `DerivedMetricsAdapter` gets a new `_update_energy()` method that resolves the electricity consumption source (external > gateway > calculated), accumulates cost when a price entity is configured, and injects both `power_consumption` and `electricity_cost` into the data dict. The base sensor's custom `_get_energy_value()` cascade is removed — `power_consumption` becomes a standard `value_fn` reader like all other derived sensors.

**Tech Stack:** Python, Home Assistant custom component patterns, voluptuous, pytest

**Spec:** `docs/superpowers/specs/2026-04-01-energy-cost-estimation-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `const.py` | New `CONF_ELECTRICITY_PRICE_ENTITY` constant |
| `config_flow.py` | Add price entity selector to `POWER_SCHEMA` and options flow |
| `repairs.py` | New `EnergyCostRepairFlow` for onboarding existing users |
| `__init__.py` | Create repair issue at setup, restore `electricity_cost` state |
| `adapters/derived_metrics.py` | New `_update_energy()`: resolve source, accumulate cost, inject data |
| `entities/base/sensor/base.py` | Remove `_get_energy_value()` and `power_consumption` special cases |
| `entities/power/sensors.py` | Add `electricity_cost` sensor description, update `power_consumption` attributes |
| `translations/en.json` | Config flow, options flow, repair flow, and entity translations |
| `tests/adapters/test_derived_metrics.py` | Tests for energy resolution and cost accumulation |

---

### Task 1: Add constant and config flow field

**Files:**
- Modify: `custom_components/hitachi_yutaki/const.py`
- Modify: `custom_components/hitachi_yutaki/config_flow.py`

- [ ] **Step 1: Add `CONF_ELECTRICITY_PRICE_ENTITY` to `const.py`**

In `const.py`, add after line 106 (`CONF_ENERGY_ENTITY`):

```python
CONF_ELECTRICITY_PRICE_ENTITY = "electricity_price_entity"
```

- [ ] **Step 2: Add field to `POWER_SCHEMA` in `config_flow.py`**

In `config_flow.py`, add the import of the new constant to the existing import block and add the field at the end of `POWER_SCHEMA` (after the `CONF_WATER_OUTLET_TEMP_ENTITY` entry, before the closing `}`):

```python
vol.Optional(CONF_ELECTRICITY_PRICE_ENTITY): selector.EntitySelector(
    selector.EntitySelectorConfig(
        domain=["sensor", "number", "input_number"],
    ),
),
```

- [ ] **Step 3: Add field to options flow `async_step_sensors()`**

In `config_flow.py`, in the `async_step_sensors()` method, add the field after the `CONF_WATER_OUTLET_TEMP_ENTITY` block (before the closing `}` of the schema dict):

```python
vol.Optional(
    CONF_ELECTRICITY_PRICE_ENTITY,
    default=(
        data.get(CONF_ELECTRICITY_PRICE_ENTITY)
        if data.get(CONF_ELECTRICITY_PRICE_ENTITY) is not None
        else vol.UNDEFINED
    ),
): selector.EntitySelector(
    selector.EntitySelectorConfig(
        domain=["sensor", "number", "input_number"],
    ),
),
```

- [ ] **Step 4: Commit**

```bash
git add custom_components/hitachi_yutaki/const.py custom_components/hitachi_yutaki/config_flow.py
git commit -m "feat: add electricity_price_entity config field"
```

---

### Task 2: Add translations

**Files:**
- Modify: `custom_components/hitachi_yutaki/translations/en.json`

- [ ] **Step 1: Add config flow label**

In `translations/en.json`, in the `config.step.power.data` object (around line 191), add:

```json
"electricity_price_entity": "Electricity Price Sensor (Optional)"
```

- [ ] **Step 2: Add options flow label**

In `translations/en.json`, in the `options.step.sensors.data` object (around line 116), add:

```json
"electricity_price_entity": "Electricity Price Sensor (Optional)"
```

- [ ] **Step 3: Add data description for both config and options**

In `translations/en.json`, add a `data_description` key inside `config.step.power` (after `data`):

```json
"data_description": {
  "electricity_price_entity": "A sensor providing the current electricity price in your currency per kWh (e.g. 0.18 for 0.18 €/kWh). Enables the electricity cost sensor."
}
```

Add the same `data_description` key inside `options.step.sensors` (after `data`):

```json
"data_description": {
  "electricity_price_entity": "A sensor providing the current electricity price in your currency per kWh (e.g. 0.18 for 0.18 €/kWh). Enables the electricity cost sensor."
}
```

- [ ] **Step 4: Add repair flow translations**

In `translations/en.json`, in the `issues` object (after `enable_telemetry`), add:

```json
"enable_energy_cost": {
  "title": "Track Your Heat Pump's Electricity Cost",
  "fix_flow": {
    "step": {
      "confirm": {
        "title": "Electricity Cost Tracking",
        "description": "You can now track the electricity cost of your heat pump. Provide a sensor that exposes the current electricity price in your currency per kWh, and the integration will compute a cumulative cost sensor.\n\nYou can change this at any time in the integration options.",
        "data": {
          "electricity_price_entity": "Electricity Price Sensor"
        },
        "data_description": {
          "electricity_price_entity": "A sensor providing the current electricity price in your currency per kWh (e.g. 0.18 for 0.18 €/kWh)."
        }
      }
    }
  }
}
```

- [ ] **Step 5: Add entity translation**

In `translations/en.json`, in the `entity.sensor` object, add:

```json
"electricity_cost": {
  "name": "Electricity Cost"
}
```

- [ ] **Step 6: Commit**

```bash
git add custom_components/hitachi_yutaki/translations/en.json
git commit -m "feat: add electricity cost translations"
```

---

### Task 3: Add repair flow

**Files:**
- Modify: `custom_components/hitachi_yutaki/repairs.py`
- Modify: `custom_components/hitachi_yutaki/__init__.py`

- [ ] **Step 1: Add `EnergyCostRepairFlow` to `repairs.py`**

Add the import of `CONF_ELECTRICITY_PRICE_ENTITY` to the existing import from `.const`:

```python
from .const import CONF_ELECTRICITY_PRICE_ENTITY, CONF_TELEMETRY_LEVEL, DEFAULT_TELEMETRY_LEVEL, DOMAIN
```

Add the new class after `EnableTelemetryRepairFlow`:

```python
class EnergyCostRepairFlow(RepairsFlow):
    """Handler for repair flow to configure electricity price sensor."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Redirect to the confirm step."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the electricity price entity selection step."""
        entry_id = self.issue_id.replace("enable_energy_cost_", "")

        config_entries = self.hass.config_entries.async_entries(DOMAIN)
        entry = next((e for e in config_entries if e.entry_id == entry_id), None)

        if entry is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            price_entity = user_input.get(CONF_ELECTRICITY_PRICE_ENTITY)
            if price_entity:
                new_data = {**entry.data, CONF_ELECTRICITY_PRICE_ENTITY: price_entity}
                self.hass.config_entries.async_update_entry(entry, data=new_data)

            async_delete_issue(self.hass, DOMAIN, self.issue_id)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ELECTRICITY_PRICE_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor", "number", "input_number"],
                        ),
                    ),
                }
            ),
        )
```

Update `async_create_fix_flow()` to route the new issue type:

```python
async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow based on the issue type."""
    if issue_id.startswith("enable_energy_cost_"):
        return EnergyCostRepairFlow()
    if issue_id.startswith("enable_telemetry_"):
        return EnableTelemetryRepairFlow()
    return MissingConfigRepairFlow()
```

- [ ] **Step 2: Create repair issue in `__init__.py`**

In `__init__.py`, add `CONF_ELECTRICITY_PRICE_ENTITY` to the import from `.const`.

After the telemetry onboarding issue block (around line 415), add:

```python
# Energy cost onboarding: suggest price entity configuration
if CONF_ELECTRICITY_PRICE_ENTITY not in entry.data:
    async_create_issue(
        hass,
        DOMAIN,
        f"enable_energy_cost_{entry.entry_id}",
        is_fixable=True,
        is_persistent=True,
        severity=IssueSeverity.WARNING,
        issue_domain=DOMAIN,
        translation_key="enable_energy_cost",
    )
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/hitachi_yutaki/repairs.py custom_components/hitachi_yutaki/__init__.py
git commit -m "feat: add energy cost repair flow for onboarding"
```

---

### Task 4: Add energy resolution and cost accumulation to DerivedMetricsAdapter

**Files:**
- Modify: `custom_components/hitachi_yutaki/adapters/derived_metrics.py`
- Test: `tests/adapters/test_derived_metrics.py`

- [ ] **Step 1: Write tests for energy resolution and cost accumulation**

Add the following tests to `tests/adapters/test_derived_metrics.py`:

```python
import time


class TestEnergyResolution:
    """Tests for electrical energy source resolution and cost accumulation."""

    def test_power_consumption_injected_from_gateway(self):
        """power_consumption is injected from gateway data when no external entity."""
        adapter = _make_adapter()
        data = _sample_data(power_consumption=42.5)
        adapter.update(data)
        assert data["power_consumption"] == 42.5
        assert data["_energy_source"] == "gateway"

    def test_power_consumption_from_electrical_power_fallback(self):
        """power_consumption is accumulated from electrical_power when no counter."""
        adapter = _make_adapter()
        # First update to set baseline
        data1 = _sample_data(compressor_current=8.5)
        adapter.update(data1)
        # Second update after a short delay
        time.sleep(0.01)
        data2 = _sample_data(compressor_current=8.5)
        adapter.update(data2)
        assert data2["_energy_source"] == "calculated"
        assert "power_consumption" in data2

    def test_power_consumption_external_entity(self):
        """power_consumption is read from external entity when configured."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "123.45"
        mock_hass.states.get.return_value = mock_state

        config_entry = MagicMock()
        config_entry.data = {"energy_entity": "sensor.external_energy"}

        adapter = DerivedMetricsAdapter(
            hass=mock_hass,
            config_entry=config_entry,
            power_supply="single",
        )
        data = _sample_data()
        adapter.update(data)
        assert data["power_consumption"] == 123.45
        assert data["_energy_source"] == "external"

    def test_electricity_cost_not_injected_without_price_entity(self):
        """electricity_cost is not in data when no price entity configured."""
        adapter = _make_adapter()
        data = _sample_data(power_consumption=42.5)
        adapter.update(data)
        assert "electricity_cost" not in data

    def test_electricity_cost_accumulated_with_price_entity(self):
        """electricity_cost accumulates delta_kWh * price."""
        mock_hass = MagicMock()

        # Price entity returns 0.18
        price_state = MagicMock()
        price_state.state = "0.18"
        # Energy entity returns increasing values
        energy_state_1 = MagicMock()
        energy_state_1.state = "100.0"
        energy_state_2 = MagicMock()
        energy_state_2.state = "102.0"  # +2 kWh

        config_entry = MagicMock()
        config_entry.data = {
            "energy_entity": "sensor.energy",
            "electricity_price_entity": "sensor.price",
        }

        def states_get(entity_id):
            if entity_id == "sensor.price":
                return price_state
            if entity_id == "sensor.energy":
                return mock_hass._energy_state
            return None

        mock_hass.states.get = states_get
        mock_hass._energy_state = energy_state_1

        adapter = DerivedMetricsAdapter(
            hass=mock_hass,
            config_entry=config_entry,
            power_supply="single",
        )

        # First update: sets baseline, no cost yet
        data1 = _sample_data()
        adapter.update(data1)
        assert data1["electricity_cost"] == 0

        # Second update: energy increased by 2 kWh at 0.18/kWh
        mock_hass._energy_state = energy_state_2
        data2 = _sample_data()
        adapter.update(data2)
        assert data2["electricity_cost"] == pytest.approx(0.36, abs=0.01)

    def test_electricity_cost_stalls_when_price_unavailable(self):
        """electricity_cost does not accumulate when price entity is unavailable."""
        mock_hass = MagicMock()

        price_state = MagicMock()
        price_state.state = "unavailable"
        energy_state = MagicMock()
        energy_state.state = "100.0"

        config_entry = MagicMock()
        config_entry.data = {
            "energy_entity": "sensor.energy",
            "electricity_price_entity": "sensor.price",
        }

        def states_get(entity_id):
            if entity_id == "sensor.price":
                return price_state
            if entity_id == "sensor.energy":
                return energy_state
            return None

        mock_hass.states.get = states_get

        adapter = DerivedMetricsAdapter(
            hass=mock_hass,
            config_entry=config_entry,
            power_supply="single",
        )

        data1 = _sample_data()
        adapter.update(data1)
        data2 = _sample_data()
        adapter.update(data2)
        assert data2["electricity_cost"] == 0

    def test_electricity_cost_restore(self):
        """restore_electricity_cost restores the accumulated cost."""
        mock_hass = MagicMock()
        price_state = MagicMock()
        price_state.state = "0.18"
        energy_state = MagicMock()
        energy_state.state = "100.0"

        config_entry = MagicMock()
        config_entry.data = {
            "energy_entity": "sensor.energy",
            "electricity_price_entity": "sensor.price",
        }

        def states_get(entity_id):
            if entity_id == "sensor.price":
                return price_state
            if entity_id == "sensor.energy":
                return energy_state
            return None

        mock_hass.states.get = states_get

        adapter = DerivedMetricsAdapter(
            hass=mock_hass,
            config_entry=config_entry,
            power_supply="single",
        )
        adapter.restore_electricity_cost(50.25)

        data = _sample_data()
        adapter.update(data)
        assert data["electricity_cost"] >= 50.25

    def test_gap_detection_skips_accumulation(self):
        """Cost is not accumulated when time gap exceeds 2x poll interval."""
        mock_hass = MagicMock()
        price_state = MagicMock()
        price_state.state = "0.18"
        energy_state_1 = MagicMock()
        energy_state_1.state = "100.0"
        energy_state_2 = MagicMock()
        energy_state_2.state = "200.0"  # huge jump

        config_entry = MagicMock()
        config_entry.data = {
            "energy_entity": "sensor.energy",
            "electricity_price_entity": "sensor.price",
        }

        def states_get(entity_id):
            if entity_id == "sensor.price":
                return price_state
            if entity_id == "sensor.energy":
                return mock_hass._energy_state
            return None

        mock_hass.states.get = states_get
        mock_hass._energy_state = energy_state_1

        adapter = DerivedMetricsAdapter(
            hass=mock_hass,
            config_entry=config_entry,
            power_supply="single",
        )

        data1 = _sample_data()
        adapter.update(data1)

        # Simulate a long gap by manipulating _last_energy_time
        adapter._last_energy_time = adapter._last_energy_time - 60  # 60s ago

        mock_hass._energy_state = energy_state_2
        data2 = _sample_data()
        adapter.update(data2)
        # Cost should NOT have been accumulated due to gap
        assert data2["electricity_cost"] == 0
```

Add `import pytest` at the top of the file if not already present.

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `_energy_source`, `electricity_cost`, `restore_electricity_cost`, `_last_energy_time` not defined.

- [ ] **Step 3: Implement energy resolution and cost accumulation in `DerivedMetricsAdapter`**

In `adapters/derived_metrics.py`, add the imports:

```python
import time

from ..const import (
    CONF_ELECTRICITY_PRICE_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_WATER_INLET_TEMP_ENTITY,
    CONF_WATER_OUTLET_TEMP_ENTITY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
```

(Replace the existing imports from `..const` with this expanded list.)

Add these instance variables at the end of `__init__()` (after the secondary timing block):

```python
# Energy resolution state
self._last_energy_value: float | None = None
self._last_energy_time: float | None = None
self._accumulated_energy: float = 0.0  # kWh from power integration fallback
self._electricity_cost: float = 0.0
```

Add a new method `_get_float_from_entity()`:

```python
def _get_float_from_entity(self, entity_id: str) -> float | None:
    """Read a float value from a HA entity state."""
    if self._hass is None or not entity_id:
        return None
    state = self._hass.states.get(entity_id)
    if state and state.state not in (None, "unknown", "unavailable"):
        try:
            return float(state.state)
        except ValueError:
            pass
    return None
```

Add the `_update_energy()` method:

```python
def _update_energy(self, data: dict[str, Any]) -> None:
    """Resolve electrical energy source, accumulate cost, inject into data."""
    now = time.monotonic()
    energy_value: float | None = None
    energy_source: str = "calculated"

    # Cascade: external > gateway > calculated
    external_entity = self._config_entry_data.get(CONF_ENERGY_ENTITY)
    if external_entity:
        energy_value = self._get_float_from_entity(external_entity)
        if energy_value is not None:
            energy_source = "external"

    if energy_value is None:
        gateway_value = data.get("power_consumption")
        if gateway_value is not None:
            energy_value = gateway_value
            energy_source = "gateway"

    if energy_value is None:
        # Fallback: integrate electrical_power over time
        electrical_power = data.get("electrical_power", 0)
        if self._last_energy_time is not None and electrical_power > 0:
            dt = now - self._last_energy_time
            if dt <= DEFAULT_SCAN_INTERVAL * 2:
                self._accumulated_energy += electrical_power * (dt / 3600)
        energy_value = round(self._accumulated_energy, 3)
        energy_source = "calculated"

    # Inject resolved energy into data
    data["power_consumption"] = energy_value
    data["_energy_source"] = energy_source

    # Cost accumulation
    price_entity = self._config_entry_data.get(CONF_ELECTRICITY_PRICE_ENTITY)
    if price_entity:
        price = self._get_float_from_entity(price_entity)
        data["_current_price"] = price

        if (
            price is not None
            and energy_value is not None
            and self._last_energy_value is not None
            and self._last_energy_time is not None
        ):
            dt = now - self._last_energy_time
            if dt <= DEFAULT_SCAN_INTERVAL * 2:
                if energy_source in ("external", "gateway"):
                    delta_kwh = energy_value - self._last_energy_value
                else:
                    # For calculated source, delta is already in accumulated_energy
                    electrical_power = data.get("electrical_power", 0)
                    delta_kwh = electrical_power * (dt / 3600) if electrical_power > 0 else 0

                if delta_kwh > 0:
                    self._electricity_cost += round(delta_kwh * price, 6)

        data["electricity_cost"] = round(self._electricity_cost, 2)

    # Track for next cycle
    self._last_energy_value = energy_value
    self._last_energy_time = now
```

Add the restore method after `restore_thermal_energy()`:

```python
def restore_electricity_cost(self, value: float) -> None:
    """Restore electricity cost state from HA last state cache."""
    self._electricity_cost = value
```

Update the `update()` method to call `_update_energy()`. Add it after `_update_cop()` (which computes `electrical_power` needed by the fallback):

```python
def update(self, data: dict[str, Any]) -> None:
    """Enrich data dict with all derived metrics."""
    # Update defrost guard first
    water_inlet = data.get("water_inlet_temp")
    water_outlet = data.get("water_outlet_temp")
    delta_t = (
        (water_outlet - water_inlet)
        if water_inlet is not None and water_outlet is not None
        else None
    )
    is_defrosting = data.get("is_defrosting", False)
    self.defrost_guard.update(is_defrosting=is_defrosting, delta_t=delta_t)

    self._update_thermal(data)
    self._update_cop(data)
    self._update_energy(data)
    self._update_timing(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/hitachi_yutaki/adapters/derived_metrics.py tests/adapters/test_derived_metrics.py
git commit -m "feat: centralize energy resolution and cost accumulation in adapter"
```

---

### Task 5: Refactor base sensor to remove `_get_energy_value()`

**Files:**
- Modify: `custom_components/hitachi_yutaki/entities/base/sensor/base.py`
- Modify: `custom_components/hitachi_yutaki/entities/power/sensors.py`

- [ ] **Step 1: Remove `_get_energy_value()` and `power_consumption` special cases from base sensor**

In `entities/base/sensor/base.py`:

Remove `CONF_ENERGY_ENTITY` from the import:

```python
from ....const import (
    DEVICE_TYPES,
    DOMAIN,
)
```

Delete the `_get_energy_value()` method (lines 123-132).

Simplify `native_value` to remove the `power_consumption` special case:

```python
@property
def native_value(self) -> StateType:
    """Return the state of the sensor."""
    if self.coordinator.data is None:
        return None

    if self.entity_description.value_fn:
        return self.entity_description.value_fn(self.coordinator)

    return None
```

Remove the `power_consumption` branch from `extra_state_attributes`:

```python
@property
def extra_state_attributes(self) -> dict[str, Any] | None:
    """Return the state attributes of the sensor."""
    if self.entity_description.attributes_fn is not None:
        return self.entity_description.attributes_fn(self.coordinator)

    key = self.entity_description.key

    # Dispatch attributes based on sensor key
    if key == "alarm":
        return self._get_alarm_attributes()
    elif key == "operation_state":
        return self._get_operation_state_attributes()

    return None
```

- [ ] **Step 2: Update `power_consumption` sensor description with `attributes_fn`**

In `entities/power/sensors.py`, add the `CONF_ELECTRICITY_PRICE_ENTITY` import and update the sensor description to include attributes:

```python
"""Power sensor descriptions and builders (electrical consumption)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.entity import EntityCategory

from ...const import CONF_ELECTRICITY_PRICE_ENTITY, DEVICE_CONTROL_UNIT
from ..base.sensor import (
    HitachiYutakiSensor,
    HitachiYutakiSensorEntityDescription,
    _create_sensors,
)

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator


def build_power_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build power sensor entities (electrical consumption + cost)."""
    descriptions = _build_power_sensor_descriptions(coordinator)
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT)


def _build_power_sensor_descriptions(
    coordinator: HitachiYutakiDataCoordinator,
) -> tuple[HitachiYutakiSensorEntityDescription, ...]:
    """Build power sensor descriptions."""
    descriptions: list[HitachiYutakiSensorEntityDescription] = [
        HitachiYutakiSensorEntityDescription(
            key="power_consumption",
            translation_key="power_consumption",
            description="Total electrical energy consumed by the unit",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            value_fn=lambda c: c.data.get("power_consumption"),
            attributes_fn=lambda c: {"energy_source": c.data.get("_energy_source", "gateway")},
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ]

    # Electricity cost sensor — only when price entity is configured
    if coordinator.config_entry.data.get(CONF_ELECTRICITY_PRICE_ENTITY):
        currency = coordinator.hass.config.currency
        descriptions.append(
            HitachiYutakiSensorEntityDescription(
                key="electricity_cost",
                translation_key="electricity_cost",
                description="Cumulative electricity cost of the heat pump",
                device_class=SensorDeviceClass.MONETARY,
                state_class=SensorStateClass.TOTAL_INCREASING,
                native_unit_of_measurement=currency,
                value_fn=lambda c: c.data.get("electricity_cost"),
                attributes_fn=lambda c: {
                    "price_entity": c.config_entry.data.get(CONF_ELECTRICITY_PRICE_ENTITY),
                    "current_price": c.data.get("_current_price"),
                    "energy_source": c.data.get("_energy_source", "gateway"),
                },
            ),
        )

    return tuple(descriptions)
```

Note: `build_power_sensors` signature changed — the `_build_power_sensor_descriptions` now takes `coordinator` to check config and read currency. Update the call in `build_power_sensors` accordingly.

- [ ] **Step 3: Run tests**

Run: `make test`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add custom_components/hitachi_yutaki/entities/base/sensor/base.py custom_components/hitachi_yutaki/entities/power/sensors.py
git commit -m "refactor: remove _get_energy_value, power_consumption reads from adapter"
```

---

### Task 6: State restoration for electricity_cost

**Files:**
- Modify: `custom_components/hitachi_yutaki/__init__.py`

- [ ] **Step 1: Add `electricity_cost` to state restoration**

In `__init__.py`, after the `_async_restore_thermal_energy()` call (around line 288), add:

```python
# Restore electricity cost from last known state
if CONF_ELECTRICITY_PRICE_ENTITY in entry.data:
    entity_registry = er.async_get(hass)
    unique_id = f"{entry.entry_id}_electricity_cost"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    if entity_id:
        restore_data = async_get_restore_data(hass)
        if entity_id in restore_data.last_states:
            last = restore_data.last_states[entity_id]
            if (
                last
                and last.state
                and last.state.state not in (None, "unknown", "unavailable", "")
            ):
                with suppress(ValueError, TypeError):
                    coordinator.derived_metrics.restore_electricity_cost(
                        float(last.state.state)
                    )
```

Note: `async_get_restore_data` and `suppress` are already imported in `__init__.py`. `CONF_ELECTRICITY_PRICE_ENTITY` was added in Task 3.

- [ ] **Step 2: Run tests**

Run: `make test`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add custom_components/hitachi_yutaki/__init__.py
git commit -m "feat: restore electricity_cost state on restart"
```

---

### Task 7: Verify sensor.py platform registers power sensors

**Files:**
- Check: `custom_components/hitachi_yutaki/sensor.py`

- [ ] **Step 1: Verify `build_power_sensors` is called with correct arguments**

Check `sensor.py` to confirm that `build_power_sensors(coordinator, entry_id)` is called. Since we changed `_build_power_sensor_descriptions` to take `coordinator`, we need to make sure `build_power_sensors` passes it correctly. The change in Task 5 already handles this — `build_power_sensors` passes `coordinator` to `_build_power_sensor_descriptions(coordinator)`.

Run: `make test`
Expected: All tests PASS.

- [ ] **Step 2: Run full check**

Run: `make check`
Expected: All linting and formatting checks PASS.

- [ ] **Step 3: Commit (if any lint fixes needed)**

```bash
git add -u
git commit -m "fix: lint fixes"
```

---

### Task 8: Final integration test

- [ ] **Step 1: Run full test suite**

Run: `make test`
Expected: All tests PASS.

- [ ] **Step 2: Run full quality checks**

Run: `make check`
Expected: All checks PASS.

- [ ] **Step 3: Update CHANGELOG.md**

Add under `[Unreleased]`:

```markdown
### Added
- Electricity cost estimation sensor — configure an electricity price entity to track cumulative energy costs
- Repair flow to onboard existing users to the electricity cost feature

### Changed
- Electrical energy resolution centralized in DerivedMetricsAdapter (internal refactor, no user-facing change)
- `power_consumption` sensor now reads from adapter like all other derived sensors
```

- [ ] **Step 4: Commit changelog**

```bash
git add CHANGELOG.md
git commit -m "docs: update changelog for electricity cost feature"
```
