# Entities Layer - Home Assistant Integration

## Overview

The `entities/` folder contains all Home Assistant entities for the Hitachi Yutaki integration. This layer implements the hexagonal architecture by connecting Home Assistant's entity system with the domain services through adapters.

## Architecture

The entities layer follows a modular structure where each device component has its own subfolder, making the codebase maintainable and scalable.

## Structure

```
entities/
├── base/              # Base entity classes and descriptions
├── circuit/           # Circuit-related entities
├── compressor/        # Compressor-related entities
├── control_unit/      # Control unit entities
├── dhw/              # Domestic Hot Water entities
├── gateway/          # Gateway entities
├── hydraulic/        # Hydraulic system entities
├── performance/      # Performance monitoring entities
├── pool/             # Pool-related entities
├── power/            # Power-related entities
└── thermal/          # Thermal system entities
```

## Base Entities

The `base/` folder contains the foundational entity classes that all other entities inherit from:

### Entity Types
- **Sensor** : Data reading entities (temperatures, power, COP, etc.)
- **Binary Sensor** : On/off state entities (alarms, status flags)
- **Switch** : Control entities for enabling/disabling features
- **Number** : Numeric input entities for settings and thresholds
- **Select** : Dropdown selection entities for modes and options
- **Button** : Action entities for manual operations
- **Climate** : HVAC control entities
- **Water Heater** : Water heating control entities

### Key Features
- **Domain Integration** : All entities use domain services through adapters
- **Coordinator Integration** : Entities are connected to the data coordinator
- **Restore State** : Entities can restore their previous state on restart
- **Device Info** : Proper device information for Home Assistant
- **Conditional Creation** : Entities can be conditionally created based on device capabilities

## Device-Specific Modules

Each device component has its own module with specialized entities:

### Circuit Module (`circuit/`)
- Climate control for heating/cooling circuits
- Temperature setpoints and modes
- Flow control and pump settings

### Compressor Module (`compressor/`)
- Compressor status and alarms
- Runtime and cycle information
- Performance metrics

### Control Unit Module (`control_unit/`)
- System status and diagnostics
- Configuration settings
- Error reporting

### DHW Module (`dhw/`)
- Domestic hot water control
- Temperature settings and schedules
- Water heater functionality

### Gateway Module (`gateway/`)
- Communication status
- Network information
- System connectivity

### Hydraulic Module (`hydraulic/`)
- Pump status and control
- Flow monitoring
- Pressure readings

### Performance Module (`performance/`)
- COP calculations
- Energy efficiency metrics
- Thermal power measurements

### Pool Module (`pool/`)
- Pool heating control
- Temperature management
- Pool-specific settings

### Power Module (`power/`)
- Electrical power monitoring
- Current and voltage readings
- Power consumption tracking

### Thermal Module (`thermal/`)
- Thermal energy calculations
- Heat transfer monitoring
- Temperature differentials

## Domain Integration

Entities integrate with the domain layer through adapters:

```python
# Example: COP sensor initialization
if description.key.startswith("cop_"):
    storage = InMemoryStorage(max_len=COP_MEASUREMENTS_HISTORY_SIZE)
    accumulator = EnergyAccumulator(
        storage=storage, period=COP_MEASUREMENTS_PERIOD
    )
    electrical_calculator = ElectricalPowerCalculatorAdapter(
        hass=coordinator.hass,
        config_entry=coordinator.config_entry,
        power_supply=coordinator.config_entry.data.get(
            CONF_POWER_SUPPLY, DEFAULT_POWER_SUPPLY
        ),
    )
    
    self._cop_service = COPService(
        accumulator=accumulator,
        thermal_calculator=thermal_power_calculator_wrapper,
        electrical_calculator=electrical_calculator,
    )
```

## Entity Creation Pattern

Entities are created using factory functions:

```python
def _create_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    descriptions: tuple[HitachiYutakiSensorEntityDescription, ...],
    device_type: DEVICE_TYPES,
) -> list[HitachiYutakiSensor]:
    """Create sensor entities for a specific device type."""
    return [
        HitachiYutakiSensor(
            coordinator=coordinator,
            description=description,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry_id}_{device_type}")},
            ),
        )
        for description in descriptions
        if description.condition is None or description.condition(coordinator)
    ]
```

## Benefits of Modular Structure

- 🔧 **Maintainability** : Each device component is isolated
- 📈 **Scalability** : Easy to add new device types
- 🧪 **Testability** : Components can be tested independently
- 🔄 **Reusability** : Base classes can be reused across modules
- 🐛 **Debugging** : Issues are easier to locate and fix
- 👥 **Team Development** : Multiple developers can work on different modules

## Migration from Monolithic sensor.py

This modular structure replaces the previous monolithic `sensor.py` approach:

**Before** : Single large file with all entities
**After** : Organized modules by device functionality

**Benefits** :
- Easier navigation and maintenance
- Better separation of concerns
- Improved code organization
- Enhanced developer experience

## Adding New Entities

To add new entities:

1. **Choose the appropriate module** based on device functionality
2. **Create entity descriptions** with proper configuration
3. **Implement the entity class** inheriting from base classes
4. **Add factory function** for entity creation
5. **Update module's `__init__.py`** to export new entities
6. **Add conditional logic** if needed for device-specific features

## Best Practices

1. **Always inherit from base classes** for consistency
2. **Use domain services** through adapters, never direct calculations
3. **Implement proper error handling** for HA state management
4. **Add device info** for proper Home Assistant integration
5. **Use conditional creation** for device-specific features
6. **Document entity purposes** and configuration options
7. **Follow naming conventions** for consistency across modules
