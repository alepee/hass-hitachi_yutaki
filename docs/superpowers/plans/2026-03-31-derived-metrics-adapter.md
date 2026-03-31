# DerivedMetricsAdapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move COP, thermal power, and compressor timing calculations from entity sensor classes into a `DerivedMetricsAdapter` that enriches `coordinator.data` before entities and telemetry consume it. Entities become simple readers.

**Architecture:** A new `DerivedMetricsAdapter` lives in `adapters/` and orchestrates the existing domain services (COPService, ThermalPowerService, CompressorTimingService). It is instantiated in `__init__.py`, injected into the coordinator, and called in `_async_update_data()` after Modbus fetch. The entity subclasses `HitachiYutakiCOPSensor`, `HitachiYutakiThermalSensor`, and `HitachiYutakiTimingSensor` are replaced by simple `value_fn` descriptors on the base `HitachiYutakiSensor` class.

**Tech Stack:** Python 3.12, pytest, pytest-asyncio, Home Assistant DataUpdateCoordinator

**Key codebase patterns:**
- Tests: `make test` (290+ tests), `make check` (ruff lint)
- Test helpers: `_sample_data(**overrides)`, `_make_coordinator()` factory
- Domain services are HA-agnostic (no `homeassistant.*` imports)
- Adapters bridge domain ↔ HA (can import `homeassistant.*`)
- Conventional commits, no Co-Authored-By

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `adapters/derived_metrics.py` | **Create** | DerivedMetricsAdapter — orchestrates domain services, enriches data dict |
| `coordinator.py` | Modify | Call `self._derived_metrics.update(data)` in `_async_update_data()`, remove telemetry compute |
| `__init__.py` | Modify | Instantiate DerivedMetricsAdapter, inject into coordinator |
| `entities/base/sensor/base.py` | Modify | Remove `sensor_class` dispatch, add attribute-reading `value_fn` support |
| `entities/base/sensor/__init__.py` | Modify | Remove subclass re-exports |
| `entities/base/sensor/cop.py` | **Delete** | Logic moved to DerivedMetricsAdapter |
| `entities/base/sensor/thermal.py` | **Delete** | Logic moved to DerivedMetricsAdapter |
| `entities/base/sensor/timing.py` | **Delete** | Logic moved to DerivedMetricsAdapter |
| `entities/performance/sensors.py` | Modify | COP descriptions: remove `sensor_class="cop"`, add `value_fn` |
| `entities/thermal/sensors.py` | Modify | Thermal descriptions: remove `sensor_class="thermal"`, add `value_fn` + `attributes_fn` |
| `entities/compressor/sensors.py` | Modify | Timing descriptions: remove `sensor_class="timing"`, add `value_fn` |
| `tests/adapters/test_derived_metrics.py` | **Create** | Unit tests for DerivedMetricsAdapter |
| `tests/entities/base/test_sensor_dispatch.py` | Modify | Update dispatch tests (no more subclass dispatch) |

---

### Task 1: Create DerivedMetricsAdapter — Thermal domain

Extract thermal power and energy calculations from `HitachiYutakiThermalSensor` into `DerivedMetricsAdapter`. After this task, the adapter computes thermal metrics and injects them into the data dict.

**Files:**
- Create: `custom_components/hitachi_yutaki/adapters/derived_metrics.py`
- Create: `tests/adapters/__init__.py`
- Create: `tests/adapters/test_derived_metrics.py`

- [ ] **Step 1: Create test directory and write thermal tests**

Create `tests/adapters/__init__.py` (empty file).

Create `tests/adapters/test_derived_metrics.py`:

```python
"""Tests for DerivedMetricsAdapter."""

from __future__ import annotations

import pytest

from custom_components.hitachi_yutaki.adapters.derived_metrics import (
    DerivedMetricsAdapter,
)


def _sample_data(**overrides) -> dict:
    """Create a sample coordinator data dict with thermal-relevant keys."""
    data = {
        "is_available": True,
        "outdoor_temp": 5.0,
        "water_inlet_temp": 30.0,
        "water_outlet_temp": 35.0,
        "water_flow": 12.0,
        "compressor_frequency": 65.0,
        "compressor_current": 8.5,
        "unit_mode": 1,
        "operation_state": "operation_state_heat_thermo_on",
    }
    data.update(overrides)
    return data


def _make_adapter(
    *,
    has_cooling: bool = False,
    supports_secondary_compressor: bool = False,
) -> DerivedMetricsAdapter:
    """Create a minimal adapter for testing."""
    return DerivedMetricsAdapter(
        hass=None,
        config_entry_data={},
        power_supply="single",
        has_cooling=has_cooling,
        supports_secondary_compressor=supports_secondary_compressor,
    )


class TestThermalPower:
    """Tests for thermal power enrichment."""

    def test_heating_power_injected(self):
        """Thermal heating power is computed and injected into data dict."""
        adapter = _make_adapter()
        data = _sample_data()
        adapter.update(data)
        assert "thermal_power_heating" in data
        assert data["thermal_power_heating"] > 0

    def test_cooling_power_zero_when_heating(self):
        """Cooling power is 0 when outlet > inlet (heating mode)."""
        adapter = _make_adapter(has_cooling=True)
        data = _sample_data(water_outlet_temp=35.0, water_inlet_temp=30.0)
        adapter.update(data)
        assert data["thermal_power_cooling"] == 0

    def test_missing_flow_produces_zero_power(self):
        """Without water flow, thermal power should be 0."""
        adapter = _make_adapter()
        data = _sample_data(water_flow=None)
        adapter.update(data)
        assert data["thermal_power_heating"] == 0

    def test_thermal_energy_accumulates(self):
        """Thermal energy accumulates across update cycles."""
        adapter = _make_adapter()
        data = _sample_data()
        adapter.update(data)
        first_total = data.get("thermal_energy_heating_total", 0)

        # Second update — energy should grow
        import time
        time.sleep(0.01)  # tiny delay for accumulator time tracking
        data2 = _sample_data()
        adapter.update(data2)
        assert data2.get("thermal_energy_heating_total", 0) >= first_total

    def test_cooling_sensors_only_with_has_cooling(self):
        """Cooling data keys should only be present when has_cooling=True."""
        adapter_no_cool = _make_adapter(has_cooling=False)
        data1 = _sample_data()
        adapter_no_cool.update(data1)
        assert "thermal_power_cooling" not in data1

        adapter_cool = _make_adapter(has_cooling=True)
        data2 = _sample_data()
        adapter_cool.update(data2)
        assert "thermal_power_cooling" in data2

    def test_defrost_guard_integration(self):
        """When defrost guard says data unreliable, power should be zero."""
        adapter = _make_adapter()
        # Simulate defrost (is_defrosting=True triggers guard)
        adapter.defrost_guard.update(is_defrosting=True, delta_t=0)
        data = _sample_data()
        adapter.update(data)
        # Power should be 0 during defrost
        assert data["thermal_power_heating"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `adapters.derived_metrics` module does not exist

- [ ] **Step 3: Implement DerivedMetricsAdapter with thermal domain**

Create `custom_components/hitachi_yutaki/adapters/derived_metrics.py`:

```python
"""DerivedMetricsAdapter — enriches coordinator data with computed metrics.

Orchestrates domain services to compute thermal power, electrical power,
COP, and compressor timing from raw gateway data. Results are injected
into the data dict so entities and telemetry see enriched data.

Lives in the adapters layer: may access HA (for external entity readings)
and delegates computation to domain services.
"""

from __future__ import annotations

import logging
from typing import Any

from ..adapters.providers.operation_mode import resolve_operation_mode
from ..domain.services.defrost_guard import DefrostGuard
from ..domain.services.thermal import ThermalEnergyAccumulator, ThermalPowerService

_LOGGER = logging.getLogger(__name__)


class DerivedMetricsAdapter:
    """Computes derived metrics and injects them into the coordinator data dict.

    Instantiated once at integration setup. Called on every poll cycle
    via update(data) which mutates the dict in-place.
    """

    def __init__(
        self,
        hass: Any,
        config_entry_data: dict[str, Any],
        power_supply: str,
        has_cooling: bool = False,
        supports_secondary_compressor: bool = False,
    ) -> None:
        """Initialize the adapter with domain services."""
        self._hass = hass
        self._config_entry_data = config_entry_data
        self._has_cooling = has_cooling

        # Defrost guard (shared across all derived metrics)
        self.defrost_guard = DefrostGuard()

        # Thermal power service (single instance, handles heating + cooling)
        self._thermal_service = ThermalPowerService(
            accumulator=ThermalEnergyAccumulator()
        )

    def update(self, data: dict[str, Any]) -> None:
        """Enrich data dict with all derived metrics.

        Called once per poll cycle in coordinator._async_update_data().
        Mutates data in-place.
        """
        # Update defrost guard first (other services depend on it)
        water_inlet = data.get("water_inlet_temp")
        water_outlet = data.get("water_outlet_temp")
        delta_t = (
            (water_outlet - water_inlet)
            if water_inlet is not None and water_outlet is not None
            else None
        )
        is_defrosting = data.get("is_defrosting", False)
        self.defrost_guard.update(is_defrosting=is_defrosting, delta_t=delta_t)

        # Thermal power and energy
        self._update_thermal(data)

    def _get_temperature(self, data: dict[str, Any], config_key: str, fallback_key: str) -> float | None:
        """Get temperature from configured external entity or coordinator data."""
        if self._hass is not None:
            entity_id = self._config_entry_data.get(config_key)
            if entity_id:
                state = self._hass.states.get(entity_id)
                if state and state.state not in (None, "unknown", "unavailable"):
                    try:
                        return float(state.state)
                    except ValueError:
                        pass
        return data.get(fallback_key)

    def _update_thermal(self, data: dict[str, Any]) -> None:
        """Compute thermal power and energy, inject into data."""
        from ..const import CONF_WATER_INLET_TEMP_ENTITY, CONF_WATER_OUTLET_TEMP_ENTITY

        water_inlet = self._get_temperature(
            data, CONF_WATER_INLET_TEMP_ENTITY, "water_inlet_temp"
        )
        water_outlet = self._get_temperature(
            data, CONF_WATER_OUTLET_TEMP_ENTITY, "water_outlet_temp"
        )
        water_flow = data.get("water_flow")

        # When defrost guard says data is unreliable, null out temps
        if not self.defrost_guard.is_data_reliable:
            water_inlet = None
            water_outlet = None

        operation_state_raw = data.get("operation_state")
        operation_mode = resolve_operation_mode(operation_state_raw)

        self._thermal_service.update(
            water_inlet_temp=water_inlet,
            water_outlet_temp=water_outlet,
            water_flow=water_flow,
            compressor_frequency=data.get("compressor_frequency"),
            operation_mode=operation_mode,
        )

        # Inject thermal power
        data["thermal_power_heating"] = round(
            self._thermal_service.get_heating_power(), 2
        )
        if self._has_cooling:
            data["thermal_power_cooling"] = round(
                self._thermal_service.get_cooling_power(), 2
            )

        # Inject thermal energy
        data["thermal_energy_heating_daily"] = round(
            self._thermal_service.get_daily_heating_energy(), 2
        )
        data["thermal_energy_heating_total"] = round(
            self._thermal_service.get_total_heating_energy(), 2
        )
        if self._has_cooling:
            data["thermal_energy_cooling_daily"] = round(
                self._thermal_service.get_daily_cooling_energy(), 2
            )
            data["thermal_energy_cooling_total"] = round(
                self._thermal_service.get_total_cooling_energy(), 2
            )

    # -- Restore methods for HA state restoration --

    def restore_thermal_energy(self, key: str, value: float) -> None:
        """Restore thermal energy state from HA last state cache.

        Args:
            key: The data key (e.g. "thermal_energy_heating_total")
            value: The energy value to restore

        """
        restore_map = {
            "thermal_energy_heating_daily": self._thermal_service.restore_daily_heating_energy,
            "thermal_energy_heating_total": self._thermal_service.restore_total_heating_energy,
            "thermal_energy_cooling_daily": self._thermal_service.restore_daily_cooling_energy,
            "thermal_energy_cooling_total": self._thermal_service.restore_total_cooling_energy,
        }
        restore_fn = restore_map.get(key)
        if restore_fn:
            restore_fn(value)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: New thermal tests PASS, all existing tests still PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/hitachi_yutaki/adapters/derived_metrics.py tests/adapters/__init__.py tests/adapters/test_derived_metrics.py
git commit -m "feat: create DerivedMetricsAdapter with thermal domain"
```

---

### Task 2: Wire DerivedMetricsAdapter into coordinator

Connect the adapter to the coordinator: instantiate in `__init__.py`, call `update()` in `_async_update_data()`, replace the defrost guard.

**Files:**
- Modify: `custom_components/hitachi_yutaki/__init__.py`
- Modify: `custom_components/hitachi_yutaki/coordinator.py`

- [ ] **Step 1: Write test for adapter wiring**

Add to `tests/adapters/test_derived_metrics.py`:

```python
class TestCoordinatorIntegration:
    """Tests for adapter integration with coordinator data flow."""

    def test_update_enriches_data_in_place(self):
        """update() mutates the data dict — no return value needed."""
        adapter = _make_adapter()
        data = _sample_data()
        original_keys = set(data.keys())
        adapter.update(data)
        # New keys added
        assert set(data.keys()) > original_keys
        # Original keys preserved
        assert data["outdoor_temp"] == 5.0
        assert data["water_inlet_temp"] == 30.0

    def test_update_with_missing_data_does_not_crash(self):
        """update() handles missing keys gracefully."""
        adapter = _make_adapter()
        data = {"is_available": True}
        adapter.update(data)
        assert data["thermal_power_heating"] == 0
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `make test`
Expected: PASS

- [ ] **Step 3: Add DerivedMetricsAdapter to coordinator**

In `coordinator.py`, add to `__init__`:

```python
# Derived metrics (injected by async_setup_entry)
self.derived_metrics: DerivedMetricsAdapter | None = None
```

In `_async_update_data()`, after populating the data dict and before telemetry collect, add:

```python
# Enrich data with derived metrics (thermal, COP, timing)
if self.derived_metrics is not None:
    self.derived_metrics.update(data)
```

Remove the existing defrost guard update from `_async_update_data()` (the adapter now owns the defrost guard):

```python
# REMOVE these lines from coordinator:
# water_inlet = data.get("water_inlet_temp")
# water_outlet = data.get("water_outlet_temp")
# delta_t = (...)
# self.defrost_guard.update(...)
```

Update the `defrost_guard` property to delegate to the adapter:

```python
@property
def defrost_guard(self):
    """Return the defrost guard (owned by derived_metrics adapter)."""
    if self.derived_metrics is not None:
        return self.derived_metrics.defrost_guard
    return self._defrost_guard  # fallback for tests
```

- [ ] **Step 4: Instantiate adapter in `__init__.py`**

In `async_setup_entry()`, after creating the coordinator and before the first refresh, add:

```python
from .adapters.derived_metrics import DerivedMetricsAdapter

coordinator.derived_metrics = DerivedMetricsAdapter(
    hass=hass,
    config_entry_data=entry.data,
    power_supply=entry.data.get(CONF_POWER_SUPPLY, DEFAULT_POWER_SUPPLY),
    has_cooling=False,  # will be set after first refresh when system_config is known
    supports_secondary_compressor=profile.supports_secondary_compressor,
)
```

Note: `has_cooling` needs to be determined after the first refresh (it depends on `system_config`). Add a post-first-refresh update:

```python
# After first refresh, update adapter with actual cooling config
coordinator.derived_metrics._has_cooling = coordinator.has_circuit(
    CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING
)
```

- [ ] **Step 5: Run all tests**

Run: `make test`
Expected: All PASS. The adapter enriches data, but entities still compute their own values (both coexist for now).

- [ ] **Step 6: Commit**

```bash
git add custom_components/hitachi_yutaki/coordinator.py custom_components/hitachi_yutaki/__init__.py
git commit -m "feat: wire DerivedMetricsAdapter into coordinator data flow"
```

---

### Task 3: Simplify thermal entities to simple readers

Replace `HitachiYutakiThermalSensor` with `value_fn` descriptors. The adapter now provides all thermal data.

**Files:**
- Modify: `custom_components/hitachi_yutaki/entities/thermal/sensors.py`
- Modify: `custom_components/hitachi_yutaki/entities/base/sensor/base.py`
- Delete: `custom_components/hitachi_yutaki/entities/base/sensor/thermal.py`
- Modify: `custom_components/hitachi_yutaki/entities/base/sensor/__init__.py`
- Modify: `tests/entities/base/test_sensor_dispatch.py`

- [ ] **Step 1: Update thermal sensor descriptions to use value_fn**

In `entities/thermal/sensors.py`, replace all `sensor_class="thermal"` descriptions with `value_fn` lambdas:

```python
HitachiYutakiSensorEntityDescription(
    key="thermal_power_heating",
    translation_key="thermal_power_heating",
    description="Current thermal heating power output",
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="kW",
    entity_category=EntityCategory.DIAGNOSTIC,
    icon="mdi:heat-wave",
    value_fn=lambda c: c.data.get("thermal_power_heating"),
),
```

Do the same for all 6 thermal descriptions (heating power, heating daily, heating total, cooling power, cooling daily, cooling total). Remove `sensor_class="thermal"` from all.

- [ ] **Step 2: Handle thermal energy state restoration**

The thermal energy sensors (daily/total) use `RestoreEntity` to restore state after HA restart. This was previously handled in `HitachiYutakiThermalSensor.async_added_to_hass()`. Now the adapter owns the state but restoration needs HA's `async_get_last_state()`.

Add restoration logic in `__init__.py` after first refresh, using the entity registry to find thermal energy entities and restore their last state:

```python
# Restore thermal energy state from HA last state cache
async def _restore_thermal_energy_states():
    """Restore thermal energy values from last known HA states."""
    from homeassistant.helpers.restore_state import RestoreStateData
    restore_data = await RestoreStateData.async_get_instance(hass)

    energy_keys = [
        "thermal_energy_heating_daily",
        "thermal_energy_heating_total",
        "thermal_energy_cooling_daily",
        "thermal_energy_cooling_total",
    ]
    for key in energy_keys:
        unique_id = f"{entry.entry_id}_{key}"
        last_state = restore_data.last_states.get(
            er_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        )
        if last_state and last_state.state.state not in (None, "unknown", "unavailable"):
            try:
                value = float(last_state.state.state)
                coordinator.derived_metrics.restore_thermal_energy(key, value)
            except ValueError:
                pass

await _restore_thermal_energy_states()
```

Note: The implementer should verify the exact RestoreStateData API and adapt. The key idea is to call `coordinator.derived_metrics.restore_thermal_energy(key, value)` for each energy sensor.

- [ ] **Step 3: Remove thermal subclass from sensor dispatch**

In `entities/base/sensor/base.py`, remove `"thermal"` from `_CLASS_MAP` and the corresponding import.

In `entities/base/sensor/__init__.py`, remove `HitachiYutakiThermalSensor` from imports and `__all__`.

- [ ] **Step 4: Delete thermal sensor subclass**

Delete `entities/base/sensor/thermal.py`.

- [ ] **Step 5: Update dispatch tests**

In `tests/entities/base/test_sensor_dispatch.py`:
- Remove `test_thermal_description_creates_thermal_sensor`
- Update `test_mixed_descriptions_dispatch_correctly` to not include thermal
- Remove `HitachiYutakiThermalSensor` from imports

- [ ] **Step 6: Run all tests**

Run: `make test`
Expected: All PASS. Thermal sensors now read from coordinator.data.

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "refactor: simplify thermal entities to value_fn readers

Thermal power and energy are now computed by DerivedMetricsAdapter
and injected into coordinator.data. Entities read with value_fn.
HitachiYutakiThermalSensor subclass deleted."
```

---

### Task 4: Add COP domain to DerivedMetricsAdapter

Add COP computation to the adapter. This is the most complex part — 4 COP instances (heating, cooling, DHW, pool), external entity access for power/voltage, secondary compressor support, and Recorder rehydration.

**Files:**
- Modify: `custom_components/hitachi_yutaki/adapters/derived_metrics.py`
- Modify: `tests/adapters/test_derived_metrics.py`

- [ ] **Step 1: Write COP tests**

Add to `tests/adapters/test_derived_metrics.py`:

```python
class TestCOP:
    """Tests for COP enrichment."""

    def test_cop_heating_injected_when_heating(self):
        """COP heating is computed when in heating mode with valid data."""
        adapter = _make_adapter()
        data = _sample_data()
        # Need multiple updates for COP to have enough data
        # (COPService requires COP_MEASUREMENTS_INTERVAL between measurements)
        adapter.update(data)
        # COP may be None on first call (needs accumulation)
        assert "cop_heating" in data

    def test_cop_quality_injected(self):
        """COP quality assessment is injected."""
        adapter = _make_adapter()
        data = _sample_data()
        adapter.update(data)
        assert "cop_heating_quality" in data

    def test_cop_none_when_compressor_off(self):
        """COP should be None when compressor is not running."""
        adapter = _make_adapter()
        data = _sample_data(compressor_frequency=0)
        adapter.update(data)
        assert data["cop_heating"] is None

    def test_cop_cooling_only_when_has_cooling(self):
        """COP cooling key should only appear when cooling is configured."""
        adapter_no_cool = _make_adapter(has_cooling=False)
        data1 = _sample_data()
        adapter_no_cool.update(data1)
        assert "cop_cooling" not in data1

        adapter_cool = _make_adapter(has_cooling=True)
        data2 = _sample_data()
        adapter_cool.update(data2)
        assert "cop_cooling" in data2

    def test_electrical_power_injected(self):
        """Electrical power is computed and injected."""
        adapter = _make_adapter()
        data = _sample_data(compressor_current=8.5)
        adapter.update(data)
        assert "electrical_power" in data
        assert data["electrical_power"] > 0

    def test_electrical_power_zero_when_no_current(self):
        """Electrical power is 0 when compressor current is 0."""
        adapter = _make_adapter()
        data = _sample_data(compressor_current=0)
        adapter.update(data)
        assert data["electrical_power"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `cop_heating` not in data (adapter doesn't compute COP yet)

- [ ] **Step 3: Implement COP in DerivedMetricsAdapter**

In `adapters/derived_metrics.py`, add to `__init__`:

```python
from ..adapters.calculators.electrical import ElectricalPowerCalculatorAdapter
from ..adapters.calculators.thermal import (
    thermal_power_calculator_cooling_wrapper,
    thermal_power_calculator_heating_wrapper,
)
from ..adapters.storage.in_memory import InMemoryStorage
from ..domain.models.cop import COPInput
from ..domain.models.operation import MODE_COOLING, MODE_DHW, MODE_HEATING, MODE_POOL
from ..domain.services.cop import (
    COP_MEASUREMENTS_HISTORY_SIZE,
    COP_MEASUREMENTS_PERIOD,
    COPService,
    EnergyAccumulator,
)

# In __init__:
# Electrical power calculator (accesses HA state for external power entity)
self._electrical_calculator = ElectricalPowerCalculatorAdapter(
    hass=hass,
    config_entry=config_entry_data,  # Note: adapter needs config_entry, not just data
    power_supply=power_supply,
)

# COP services — one per mode
self._cop_services: dict[str, COPService] = {}
self._cop_services["cop_heating"] = self._make_cop_service(
    thermal_power_calculator_heating_wrapper, MODE_HEATING
)
if has_cooling:
    self._cop_services["cop_cooling"] = self._make_cop_service(
        thermal_power_calculator_cooling_wrapper, MODE_COOLING
    )
# DHW and pool COP added conditionally (has_dhw, has_pool params)
```

Add `_make_cop_service` helper:

```python
def _make_cop_service(self, thermal_calculator, expected_mode):
    """Create a COP service instance for a specific mode."""
    storage = InMemoryStorage(max_len=COP_MEASUREMENTS_HISTORY_SIZE)
    accumulator = EnergyAccumulator(storage=storage, period=COP_MEASUREMENTS_PERIOD)
    return COPService(
        accumulator=accumulator,
        thermal_calculator=thermal_calculator,
        electrical_calculator=self._electrical_calculator,
        expected_mode=expected_mode,
    )
```

Add `_update_cop` method:

```python
def _update_cop(self, data: dict[str, Any]) -> None:
    """Compute COP for all configured modes and inject into data."""
    # Determine HVAC action
    hvac_action = self._get_hvac_action(data)
    operation_mode = resolve_operation_mode(data.get("operation_state"))

    has_secondary = self._supports_secondary_compressor

    cop_input = COPInput(
        water_inlet_temp=self._get_temperature(data, CONF_WATER_INLET_TEMP_ENTITY, "water_inlet_temp"),
        water_outlet_temp=self._get_temperature(data, CONF_WATER_OUTLET_TEMP_ENTITY, "water_outlet_temp"),
        water_flow=data.get("water_flow"),
        compressor_current=data.get("compressor_current"),
        compressor_frequency=data.get("compressor_frequency"),
        secondary_compressor_current=(
            data.get("secondary_compressor_current") if has_secondary else None
        ),
        secondary_compressor_frequency=(
            data.get("secondary_compressor_frequency") if has_secondary else None
        ),
        hvac_action=hvac_action,
        operation_mode=operation_mode,
    )

    # Compute electrical power (for telemetry and COP)
    current = data.get("compressor_current")
    if current is not None and current > 0:
        data["electrical_power"] = round(self._electrical_calculator(current), 3)
    else:
        data["electrical_power"] = 0

    # Update each COP service and inject results
    for key, service in self._cop_services.items():
        if self.defrost_guard.is_data_reliable:
            service.update(cop_input)

        cop_value = service.get_value()
        data[key] = cop_value

        quality = service.get_quality()
        data[f"{key}_quality"] = quality.quality
        data[f"{key}_measurements"] = quality.measurements
        data[f"{key}_time_span_minutes"] = quality.time_span_minutes
```

Call `_update_cop(data)` in `update()` after `_update_thermal()`.

The implementer should also port `_get_hvac_action()` and `_detect_mode_from_temperatures()` from the COP entity — these determine whether the system is heating or cooling in AUTO mode.

- [ ] **Step 4: Run tests**

Run: `make test`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/hitachi_yutaki/adapters/derived_metrics.py tests/adapters/test_derived_metrics.py
git commit -m "feat: add COP domain to DerivedMetricsAdapter"
```

---

### Task 5: Simplify COP entities to simple readers

Replace `HitachiYutakiCOPSensor` with `value_fn` descriptors. Move Recorder rehydration to the adapter.

**Files:**
- Modify: `custom_components/hitachi_yutaki/entities/performance/sensors.py`
- Modify: `custom_components/hitachi_yutaki/entities/base/sensor/base.py`
- Modify: `custom_components/hitachi_yutaki/entities/base/sensor/__init__.py`
- Delete: `custom_components/hitachi_yutaki/entities/base/sensor/cop.py`
- Modify: `custom_components/hitachi_yutaki/adapters/derived_metrics.py`
- Modify: `custom_components/hitachi_yutaki/__init__.py`
- Modify: `tests/entities/base/test_sensor_dispatch.py`

- [ ] **Step 1: Add extra_state_attributes support to base sensor**

COP sensors expose quality attributes. The base sensor needs a way to provide attributes via description. Add to `HitachiYutakiSensorEntityDescription`:

```python
attributes_fn: Callable[[HitachiYutakiDataCoordinator], dict[str, Any] | None] | None = None
```

In `HitachiYutakiSensor.extra_state_attributes`, add before existing dispatch:

```python
if self.entity_description.attributes_fn is not None:
    return self.entity_description.attributes_fn(self.coordinator)
```

- [ ] **Step 2: Update COP descriptions to use value_fn and attributes_fn**

In `entities/performance/sensors.py`:

```python
HitachiYutakiSensorEntityDescription(
    key="cop_heating",
    translation_key="cop_heating",
    description="Coefficient of Performance for Space Heating",
    device_class=None,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    icon="mdi:heat-pump",
    condition=lambda c: (
        c.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING)
        or c.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING)
    ),
    value_fn=lambda c: c.data.get("cop_heating"),
    attributes_fn=lambda c: {
        "quality": c.data.get("cop_heating_quality"),
        "measurements": c.data.get("cop_heating_measurements"),
        "time_span_minutes": c.data.get("cop_heating_time_span_minutes"),
    },
),
```

Do the same for cop_cooling, cop_dhw, cop_pool. Remove `sensor_class="cop"` from all.

- [ ] **Step 3: Add Recorder rehydration to DerivedMetricsAdapter**

Add `async_rehydrate_cop()` method to the adapter that replays COP history for all configured modes. This method needs `hass` and entity registry access — it's an adapter method, so HA imports are allowed.

The implementer should port the rehydration logic from `HitachiYutakiCOPSensor._async_rehydrate_cop_history()` and `_async_build_cop_entity_map()`. The key difference: instead of building entity maps per-sensor, build one entity map and rehydrate all COP services.

Call `await coordinator.derived_metrics.async_rehydrate_cop()` in `__init__.py` after the first refresh.

- [ ] **Step 4: Remove COP subclass from sensor dispatch**

In `entities/base/sensor/base.py`, remove `"cop"` from `_CLASS_MAP` and the corresponding import.

In `entities/base/sensor/__init__.py`, remove `HitachiYutakiCOPSensor` from imports and `__all__`.

- [ ] **Step 5: Delete COP sensor subclass**

Delete `entities/base/sensor/cop.py`.

- [ ] **Step 6: Update dispatch tests**

In `tests/entities/base/test_sensor_dispatch.py`:
- Remove `test_cop_description_creates_cop_sensor`
- Update `test_mixed_descriptions_dispatch_correctly`
- Remove `HitachiYutakiCOPSensor` from imports

- [ ] **Step 7: Run all tests**

Run: `make test`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add -u
git commit -m "refactor: simplify COP entities to value_fn readers

COP is now computed by DerivedMetricsAdapter with full access to
external power entity and secondary compressor. Entities read from
coordinator.data. HitachiYutakiCOPSensor subclass deleted.
Recorder rehydration moved to adapter."
```

---

### Task 6: Add timing domain to DerivedMetricsAdapter

Add compressor timing calculations. Same pattern as thermal and COP.

**Files:**
- Modify: `custom_components/hitachi_yutaki/adapters/derived_metrics.py`
- Modify: `custom_components/hitachi_yutaki/entities/compressor/sensors.py`
- Modify: `custom_components/hitachi_yutaki/entities/base/sensor/base.py`
- Modify: `custom_components/hitachi_yutaki/entities/base/sensor/__init__.py`
- Delete: `custom_components/hitachi_yutaki/entities/base/sensor/timing.py`
- Modify: `tests/adapters/test_derived_metrics.py`
- Modify: `tests/entities/base/test_sensor_dispatch.py`

- [ ] **Step 1: Write timing tests**

Add to `tests/adapters/test_derived_metrics.py`:

```python
class TestTiming:
    """Tests for compressor timing enrichment."""

    def test_timing_keys_injected(self):
        """Timing data keys should be injected into data dict."""
        adapter = _make_adapter()
        data = _sample_data(compressor_frequency=65.0)
        adapter.update(data)
        assert "compressor_cycle_time" in data
        assert "compressor_runtime" in data
        assert "compressor_resttime" in data
```

- [ ] **Step 2: Implement timing in DerivedMetricsAdapter**

Add CompressorTimingService instances to the adapter (primary + optional secondary). Port the `async_update_timing()` logic from `HitachiYutakiTimingSensor`. Inject timing results into data dict.

- [ ] **Step 3: Update compressor timing entity descriptions**

In `entities/compressor/sensors.py`, replace `sensor_class="timing"` with `value_fn` lambdas. Remove the subclass.

- [ ] **Step 4: Delete timing sensor subclass**

Delete `entities/base/sensor/timing.py`. Remove from `__init__.py` and `_CLASS_MAP`.

- [ ] **Step 5: Update dispatch tests**

Remove timing from `test_sensor_dispatch.py`.

- [ ] **Step 6: Run all tests**

Run: `make test`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "refactor: simplify timing entities to value_fn readers

Compressor timing is now computed by DerivedMetricsAdapter.
HitachiYutakiTimingSensor subclass deleted."
```

---

### Task 7: Clean up sensor_class dispatch and remove telemetry compute

Now that all subclasses are gone, clean up the dispatch mechanism and remove the redundant telemetry compute in the collector.

**Files:**
- Modify: `custom_components/hitachi_yutaki/entities/base/sensor/base.py`
- Modify: `custom_components/hitachi_yutaki/telemetry/collector.py`
- Modify: `tests/entities/base/test_sensor_dispatch.py`
- Modify: `tests/test_telemetry_collector.py`

- [ ] **Step 1: Remove sensor_class dispatch from base.py**

In `entities/base/sensor/base.py`:
- Remove `sensor_class` field from `HitachiYutakiSensorEntityDescription`
- Remove `_CLASS_MAP` and the dispatch logic in `_create_sensors()`
- Remove local imports of deleted subclasses
- `_create_sensors()` now always creates `HitachiYutakiSensor`

- [ ] **Step 2: Remove telemetry collector compute**

In `telemetry/collector.py`:
- Remove the thermal_power, electrical_power, COP computation (lines 90-127 approximately)
- The collector now reads these from `data` dict directly (they were injected by the adapter)
- Remove imports of domain models/services that are no longer needed
- Remove `power_supply` parameter from constructor (no longer needed for electrical calc)

Update corresponding tests in `tests/test_telemetry_collector.py`.

- [ ] **Step 3: Update dispatch tests**

`tests/entities/base/test_sensor_dispatch.py`:
- Remove all subclass dispatch tests
- Keep `test_no_sensor_class_creates_base_sensor`, `test_condition_false_skips_entity`, `test_condition_true_creates_entity`
- Rename file if appropriate (it no longer tests dispatch, just creation)

- [ ] **Step 4: Run all tests**

Run: `make test && make check`
Expected: All PASS, no lint errors

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "refactor: remove sensor_class dispatch and telemetry compute

All sensors now use base HitachiYutakiSensor with value_fn.
Telemetry collector reads derived metrics from coordinator.data
instead of computing them. Removes domain service imports from collector."
```
