# Hitachi Integration Architecture

## Overview

This document describes the target architecture of the Home Assistant integration for Hitachi heat pumps. The main goal is to build a modular, extensible, and maintainable architecture that supports different kinds of Modbus gateways and, over time, other communication protocols as well.

The scope covers the Yutaki and Yutampo product lines.

## Architectural Approaches

### 0. Hexagonal Architecture (Ports and Adapters)

**Principle:** Clear separation between the domain (core) and technical details (adapters) through interfaces (ports).

**Structure:**
```
                    ┌──────────────────┐
                    │  Home Assistant  │  ← Input adapters
                    └─────────┬────────┘
                              │
                    ┌─────────▼────────┐
                    │   Ports (ABC)    │  ← Interfaces
                    └─────────┬────────┘
                              │
                    ┌─────────▼────────┐
                    │   Core/Domain    │  ← Business logic
                    └─────────┬────────┘
                              │
                    ┌─────────▼────────┐
                    │   Ports (ABC)    │  ← Interfaces
                    └─────────┬────────┘
                              │
                    ┌─────────▼────────┐
                    │  Modbus/TCP/etc. │  ← Output adapters
                    └──────────────────┘
```

**Implementation:**
- **Input ports:** Interfaces for Home Assistant platforms
- **Output ports:** `HitachiApiClient` (ABC), `HitachiHeatPumpProfile` (ABC)
- **Core:** `coordinator.py`, business logic, `const.py`
- **Input adapters:** `sensor.py`, `climate.py`, `water_heater.py`, etc.
- **Output adapters:** `api/modbus/`, `profiles/`, etc.

**Advantages:**
- Domain independence from technical details
- Maximum testability (mocking ports)
- Flexibility to swap implementations
- Clear separation of concerns
- Dependency inversion

**Drawbacks:**
- Higher initial complexity
- More abstractions to maintain
- Learning curve for new contributors

### 1. Separation of Concerns

**Principle:** Each module has a single, well-defined responsibility.

**Implementation:**
- `api/`: Communication with the heat pump
- `profiles/`: Business logic specific to heat pump models
- `coordinator.py`: Data update orchestration
- Entity platforms: Home Assistant UI

**Advantages:**
- Easier to understand and maintain
- Simplified unit testing
- Easier reuse
- Independent evolution of components

**Drawbacks:**
- More files to manage
- Increased initial complexity
- Risk of over-engineering for simple projects

### 2. Dependency Injection

**Principle:** Dependencies are injected into classes via the constructor rather than created internally.

**Implementation:**
```python
class HitachiDataCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: HitachiApiClient,
        profile: HitachiHeatPumpProfile,
    ):
        self.api_client = api_client
        self.profile = profile
        # ...
```

**Advantages:**
- Improved testability (easier mocking)
- Loose coupling between components
- Flexibility to swap implementations
- Adheres to dependency inversion

**Drawbacks:**
- More complex configuration
- More boilerplate code
- Learning curve for developers

### 3. Strategy Pattern

**Principle:** Use interfaces so that algorithms can be swapped at runtime.

**Implementation:**
- `HitachiApiClient` (ABC) for different protocols
- `HitachiHeatPumpProfile` (ABC) for different models
- `HitachiRegisterMap` (ABC) for different register mappings (Modbus implementation detail)

**Advantages:**
- Maximum extensibility
- Open/Closed Principle compliance
- Add new protocols/models without changing existing code
- Isolated tests per strategy

**Drawbacks:**
- Interface complexity
- Increased number of objects
- Risk of class proliferation

### 4. Factory Pattern

**Principle:** Create objects via dedicated methods instead of direct constructors.

**Implementation:**
```python
def get_heat_pump_profile(model_id: int) -> HitachiHeatPumpProfile:
    profile_class = MODEL_ID_TO_PROFILE.get(model_id, YutakiSProfile)
    return profile_class()
```

**Advantages:**
- Encapsulates creation logic
- Flexibility in selecting implementation
- Centralized configuration
- Reusability

**Drawbacks:**
- Coupling to the factory
- Factory maintenance complexity
- Less direct control over instantiation

### 5. Data-Driven Entity Creation

**Principle:** Create entities dynamically based on data descriptions instead of static code.

**Implementation:**
```python
SENSOR_DESCRIPTIONS = {
    DEVICE_TYPE_SYSTEM: [
        EntityDescription(
            key="outdoor_temperature",
            name="Outdoor Temperature",
            # ...
        ),
        # ...
    ],
    # ...
}
```

**Advantages:**
- Declarative configuration
- Add entities without code changes
- Consistency across entities
- Simplified maintenance

**Drawbacks:**
- Less flexibility for complex cases
- Dependence on data structures
- Harder debugging

## Detailed Architecture

### Module Structure

```
custom_components/hitachi_yutaki/
├── __init__.py                 # Entry point and orchestration
├── coordinator.py              # Data management and coordination
├── config_flow.py              # User configuration
├── const.py                    # Shared constants
├── api/                        # Communication layer
│   ├── __init__.py            # Abstract API interface
│   └── modbus/                # Modbus implementation
│       ├── __init__.py
│       ├── client.py          # Modbus TCP client
│       └── registers/         # Register mappings
│           ├── __init__.py    # RegisterMap interface
│           ├── atw_mbs_02.py  # ATW-MBS-02 mapping
│           └── hc_a8mb.py     # HC-A8MB mapping
├── profiles/                   # Heat pump profiles
│   ├── __init__.py            # Factory and interface
│   ├── base.py                # Abstract base class
│   ├── yutaki_s.py            # Yutaki S profile
│   ├── yutaki_s_combi.py      # Yutaki S Combi profile
│   ├── yutaki_s80.py          # Yutaki S80 profile
│   └── yutampo_r32.py         # Yutampo R32 profile
├── sensor.py                   # Sensor platform
├── binary_sensor.py            # BinarySensor platform
├── climate.py                  # Climate platform
├── water_heater.py             # WaterHeater platform
├── switch.py                   # Switch platform
├── number.py                   # Number platform
├── select.py                   # Select platform
├── button.py                   # Button platform
└── translations/               # Translations
    ├── en.json
    └── fr.json
```

### Architectural Layers (Hexagonal Architecture)

#### 1. Interface Layer

**Responsibility:** Interface with Home Assistant and handle user events.

**Components:**
- Entity platforms (`sensor.py`, `climate.py`, `water_heater.py`, etc.)
- `translations/`: Internationalization
- `config_flow.py`: User configuration

**Characteristics:**
- Coupled with Home Assistant
- User interface
- User event handling
- Implements input ports

#### 2. Application Layer

**Responsibility:** Orchestrate use cases and coordinate data.

**Components:**
- `coordinator.py`: Manage updates and data cache
- `__init__.py`: Setup and initialization

**Characteristics:**
- High-level business logic
- Application-level error handling
- Interface with Home Assistant

#### 3. Domain Layer

**Responsibility:** Business logic specific to Hitachi heat pumps.

**Components:**
- `profiles/`: Models and their capabilities
- `const.py`: Domain constants

**Characteristics:**
- Independent from infrastructure
- Centralized business rules
- Domain data models
- Definition of ports (ABC interfaces). Conceptually, these ports belong to the Domain. Practically, for code organization reasons, `HitachiApiClient` (ABC) is exposed from `api/__init__.py` and `HitachiHeatPumpProfile` (ABC) from `profiles/__init__.py`.

#### 4. Infrastructure Layer

**Responsibility:** Communicate with hardware and handle protocols.

**Components:**
- `api/modbus/client.py`: Modbus TCP client
- `api/modbus/registers/`: Register mappings specific to Modbus gateways

**Characteristics:**
- Strong coupling with the Modbus protocol
- Communication error handling
- Transport detail abstraction
- Implements output ports

**Important note:** `HitachiRegisterMap` is a Modbus-specific implementation detail. In the case of a direct TCP implementation or another protocol (such as ESPHome), this abstraction would likely not be needed. Each API client type may have its own internal abstractions tailored to its communication protocol.

### Data Flow

Example (Modbus)

```
Home Assistant
    ↓
__init__.py (Orchestration)
    ↓
coordinator.py (Coordination)
    ↓
api_client (Communication)
    ↓
register_map (Mapping)
    ↓
Modbus Gateway
    ↓
Heat Pump Hardware
```

Non‑Modbus case (generic)

```
Home Assistant
    ↓
__init__.py (Orchestration)
    ↓
coordinator.py (Coordination)
    ↓
api_client (Communication)
    ↓
protocol adapter (Direct TCP / ESPHome / …)
    ↓
Heat Pump Hardware
```

### Error Handling

#### Error levels

1. **Communication errors (Infrastructure)**
   - Modbus timeouts
   - Network connection errors
   - Protocol errors

2. **Data errors (Application)**
   - Invalid data
   - Registers not available
   - Data inconsistencies

3. **Business errors (Domain)**
   - Unsupported model
   - Capabilities not available
   - Invalid configuration

#### Handling strategies

- **Automatic retry** for transient errors
- **Fallback** to default values
- **Detailed logging** for debugging
- **User notifications** via the Issue Registry

### Extensibility

#### Adding a new Modbus gateway

1. Create a new class in `api/modbus/registers/`
2. Implement `HitachiRegisterMap`
3. Add detection logic in `config_flow.py`
4. Test with actual hardware

#### Adding a new heat pump model

1. Create a new file in `profiles/`
2. Implement `HitachiHeatPumpProfile`
3. Add the mapping in `profiles/__init__.py`
4. Define model-specific capabilities

#### Adding a new protocol (ESPHome, direct TCP, etc.)

1. Create a new module in `api/` (e.g., `api/tcp/`, `api/esphome/`)
2. Implement `HitachiApiClient`
3. Define internal abstractions specific to the protocol (not necessarily registers)
4. Adapt the detection logic
5. Update the factory

**Note:** Each protocol may have its own internal abstractions. For example, a direct TCP client might use textual commands instead of Modbus registers, and an ESPHome client might use native ESPHome entities.

### Performance and Optimization

#### Caching strategies

- **Data cache** in the coordinator
- **Register cache** to avoid repeated reads
- **Profile cache** to avoid recreation

#### Communication optimizations

- **Block reads** of contiguous registers
- **Differential updates** of entities
- **Adaptive timeout management**

### Security

#### Access management

- **Input validation** of user data
- **Sanitization** of received data
- **Privilege limitation** for writes

#### Robustness

- **Automatic reconnection handling**
- **Recovery** after errors
- **Validation** of critical data

### Testing

#### Test strategy

- **Unit tests** for each component
- **Integration tests** for full flows
- **Performance tests** for timeouts
- **Robustness tests** for errors

#### Mocking

- **Mock Modbus client** for tests
- **Mock profiles** to test different models
- **Mock Home Assistant** for integration tests
