# Adapters Layer - Hexagonal Architecture

## Overview

The `adapters/` folder contains the **concrete implementations** of the ports defined in the domain. These adapters bridge the gap between pure business logic and Home Assistant infrastructure.

## Principle

Adapters **implement** the domain interfaces (ports) and **adapt** data between the external world (HA) and the domain.

## Structure

```
adapters/
├── calculators/     # Calculator implementations
├── providers/       # Data provider implementations
└── storage/         # Storage implementations
```

## Calculators

### `calculators/electrical.py`
- `ElectricalPowerCalculatorAdapter` : Adapts HA entities to electrical calculation
- Retrieves voltage/power from configured HA entities
- Delegates calculation to `domain.services.electrical.calculate_electrical_power`

### `calculators/thermal.py`
- `thermal_power_calculator_wrapper` : Wrapper for thermal calculation
- Adapts signature for COPService
- Delegates to `domain.services.thermal.calculate_thermal_power`

## Providers

### `providers/coordinator.py`
- `CoordinatorDataProvider` : Adapts `HitachiYutakiDataCoordinator`
- Implements `DataProvider` protocol
- Methods : `get_water_inlet_temp()`, `get_water_flow()`, etc.

### `providers/entity_state.py`
- `EntityStateProvider` : Adapts HA entities states
- Implements `StateProvider` protocol
- Method : `get_float_from_entity(config_key)`

## Storage

### `storage/in_memory.py`
- `InMemoryStorage[T]` : In-memory storage implementation
- Implements `Storage[T]` protocol from domain
- Uses `collections.deque` for performance

## Usage

### In entities
```python
# Create adapters
electrical_adapter = ElectricalPowerCalculatorAdapter(hass, config_entry, power_supply)
thermal_adapter = thermal_power_calculator_wrapper
storage = InMemoryStorage(max_len=100)

# Use with domain services
cop_service = COPService(accumulator, thermal_adapter, electrical_adapter)
```

### In tests
```python
# Mock adapters for tests
class MockElectricalAdapter:
    def __call__(self, current: float) -> float:
        return current * 0.1  # Simple mock

# Test with mocks
cop_service = COPService(accumulator, thermal_adapter, MockElectricalAdapter())
```

## Patterns used

### Adapter Pattern
- Adapts HA interface to domain interface
- Masks HA complexity from domain

### Strategy Pattern
- Adapters are injected into services
- Allows easy implementation changes

### Dependency Injection
- Services receive their dependencies
- Facilitates testing and reusability

## Rules

1. **ALWAYS** implement domain protocols
2. **NEVER** expose business logic in adapters
3. **ALWAYS** delegate calculations to domain
4. **ALWAYS** handle HA errors (unknown, unavailable, etc.)
5. **ALWAYS** document adaptation parameters

## Benefits

- 🔌 **Decoupling** : Domain doesn't know HA
- 🧪 **Testability** : Easy to create mocks
- 🔄 **Reusability** : Same domain, different adapters
- 🛠️ **Maintainability** : HA changes without domain impact
- 📊 **Performance** : Adapters optimized for their context

## Extension examples

### New adapter for database
```python
# adapters/storage/database.py
class DatabaseStorage(Storage[T]):
    def __init__(self, connection):
        self._conn = connection
    
    def append(self, item: T) -> None:
        # Save to database
        pass
```

### New adapter for external API
```python
# adapters/providers/api.py
class APIDataProvider:
    def get_water_inlet_temp(self) -> float | None:
        # Retrieve from external API
        pass
```

## Migration from services/

Adapters replace the old `services/` :
- `services/electrical.py` → `adapters/calculators/electrical.py`
- `services/thermal.py` → `adapters/calculators/thermal.py`
- `services/storage/` → `adapters/storage/`

**Benefit** : Clear separation between business logic (domain) and infrastructure (adapters).
