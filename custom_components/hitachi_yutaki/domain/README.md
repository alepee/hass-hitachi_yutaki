# Domain Layer - Hexagonal Architecture

## Overview

The `domain/` folder contains the **pure business logic** of the Hitachi Yutaki integration. This layer is completely independent of Home Assistant and can be tested without any external dependencies.

## Principles

- ✅ **No external dependencies** : Only Python stdlib is allowed
- ✅ **Pure business logic** : Calculations, algorithms, business rules
- ✅ **Maximum testability** : Unit tests without mocks
- ✅ **Reusability** : Can be used by sensor, climate, water_heater, etc.

## Structure

```
domain/
├── models/          # Pure data models (dataclasses)
├── ports/           # Interfaces (Protocols) - contracts
└── services/        # Business services - pure logic
```

## Models

### `models/cop.py`
- `COPInput` : Input data for COP calculation
- `COPQuality` : Quality indicator for measurements
- `PowerMeasurement` : Power measurement with timestamp

### `models/thermal.py`
- `ThermalPowerInput` : Input data for thermal calculation
- `ThermalEnergyResult` : Complete result of thermal calculations

### `models/timing.py`
- `CompressorTimingResult` : Results of compressor timing calculations

### `models/electrical.py`
- `ElectricalPowerInput` : Input data for electrical calculation

## Ports (Interfaces)

### `ports/calculators.py`
- `ThermalPowerCalculator` : Protocol for thermal power calculation
- `ElectricalPowerCalculator` : Protocol for electrical power calculation

### `ports/providers.py`
- `DataProvider` : Protocol for heat pump data access
- `StateProvider` : Protocol for HA entities state access

### `ports/storage.py`
- `Storage[T]` : Generic interface for data storage

## Services

### `services/cop.py`
- `COPService` : Main service for COP calculation
- `EnergyAccumulator` : Energy accumulator for calculations

### `services/thermal.py`
- `ThermalPowerService` : Service for thermal calculations
- `ThermalEnergyAccumulator` : Thermal energy accumulator
- `calculate_thermal_power()` : Pure calculation function

### `services/timing.py`
- `CompressorTimingService` : Service for compressor timing
- `CompressorHistory` : Compressor state history

### `services/electrical.py`
- `calculate_electrical_power()` : Pure electrical calculation function

## Usage

### In tests
```python
# Pure test without HA dependency
from domain.services.cop import COPService, EnergyAccumulator
from domain.services.thermal import ThermalPowerService

# Create services with mocks
cop_service = COPService(accumulator, thermal_calc, electrical_calc)
thermal_service = ThermalPowerService(accumulator)

# Test business logic
result = cop_service.get_value()
```

### In adapters
```python
# Adapters implement the ports
from domain.ports.calculators import ElectricalPowerCalculator
from domain.services.electrical import calculate_electrical_power

class MyElectricalAdapter:
    def __call__(self, current: float) -> float:
        return calculate_electrical_power(ElectricalPowerInput(current=current))
```

## Strict rules

1. **NEVER** import `homeassistant.*`
2. **NEVER** import `adapters.*` or `entities.*`
3. **NEVER** import external modules (except stdlib)
4. **ALWAYS** use Protocols for dependencies
5. **ALWAYS** document public functions

## Benefits

- 🧪 **Pure unit tests** : No HA mocks needed
- 🔄 **Reusability** : Same logic for sensor, climate, etc.
- 🐛 **Easy debugging** : Isolated and testable logic
- 📈 **Scalability** : New services without impact
- 🏗️ **Clean architecture** : Clear separation of responsibilities
