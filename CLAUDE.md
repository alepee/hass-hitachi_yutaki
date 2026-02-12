# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration for Hitachi air-to-water heat pumps (Yutaki and Yutampo models). It communicates via Modbus with ATW-MBS-02 gateways and follows hexagonal architecture principles.

**Current Version**: see `manifest.json` (on branch `beta/2.0.0`)
**Main Branch for PRs**: `dev`

## Development Commands

### Setup
```bash
uv sync --group dev     # Install all dependencies (or: ./scripts/setup)
```

### Linting
```bash
uv run ruff check custom_components --fix   # Lint with auto-fix
```

### Testing
```bash
uv run pytest                  # Run all tests
uv run pytest tests/domain/    # Run domain layer tests only
```

### Home Assistant Development Instance
```bash
./scripts/develop              # Run HA with debug config
./scripts/dev-branch           # Install HA dev branch
./scripts/specific-version     # Install specific HA version
./scripts/upgrade              # Upgrade to latest HA
```

Pre-commit hooks are automatically installed by `scripts/setup` and run ruff on every commit.

## Architecture

This integration follows **Hexagonal Architecture** (Ports and Adapters) with strict separation of concerns.

### Layer Structure

```
custom_components/hitachi_yutaki/
├── domain/              # Pure business logic (NO HA dependencies)
│   ├── models/          # Data structures (dataclasses, NamedTuples)
│   ├── ports/           # Interfaces (Protocols) defining contracts
│   └── services/        # Business logic services (COP, thermal, timing)
├── adapters/            # Concrete implementations of domain ports
│   ├── calculators/     # Power calculation adapters
│   ├── providers/       # Data providers (coordinator, entity state)
│   └── storage/         # Storage implementations (in-memory)
├── entities/            # Domain-driven entity organization
│   ├── base/            # Base classes for all entity types
│   ├── performance/     # COP sensors
│   ├── thermal/         # Thermal energy sensors
│   ├── power/           # Electrical power sensors
│   ├── gateway/         # Gateway connectivity sensors
│   ├── hydraulic/       # Water pumps and hydraulic sensors
│   ├── compressor/      # Compressor sensors
│   ├── control_unit/    # Main control unit entities
│   ├── circuit/         # Heating/cooling circuit entities (climate)
│   ├── dhw/             # Domestic Hot Water entities (water_heater)
│   └── pool/            # Pool heating entities
├── api/                 # Modbus communication layer
│   └── modbus/registers/
├── profiles/            # Heat pump model profiles (Yutaki S, S80, M, etc.)
├── sensor.py            # HA platform orchestrator
├── binary_sensor.py     # HA platform orchestrator
├── climate.py           # HA platform orchestrator
└── ... (other platform files)
```

### Critical Architecture Rules

**Domain Layer** (`domain/`):
- **NEVER** import `homeassistant.*`
- **NEVER** import from `adapters.*` or `entities.*`
- **NEVER** use external libraries (stdlib only)
- **ALWAYS** use Protocols for dependencies
- Pure business logic that can be tested without HA mocks

**Adapters Layer** (`adapters/`):
- Implements domain ports/protocols
- Bridges domain with Home Assistant infrastructure
- Delegates business logic to domain services
- Handles HA-specific concerns (state retrieval, entity data)

**Entity Layer** (`entities/`):
- Organized by **business domain** (not by entity type)
- Each domain has builder functions that return entity lists
- Uses base classes from `entities/base/` for common HA entity patterns
- Platform files (`sensor.py`, etc.) call builders and register entities

### Entity Builder Pattern

Each domain exports builder functions:

```python
# entities/<domain>/sensors.py
def build_<domain>_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    # domain-specific params (circuit_id, etc.)
) -> list[SensorEntity]:
    """Build sensor entities for <domain>."""
    descriptions = _build_<domain>_sensor_descriptions()
    from ..base.sensor import _create_sensors
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_TYPE)
```

Platform files orchestrate by calling builders:
```python
# sensor.py
async def async_setup_entry(...):
    entities = []
    entities.extend(build_gateway_sensors(coordinator, entry.entry_id))
    entities.extend(build_performance_sensors(coordinator, entry.entry_id))
    # ... etc
    async_add_entities(entities)
```

## Key Domain Concepts

### Heat Pump Profiles
- Auto-detected based on Modbus data
- Defines capabilities: DHW, pool, circuits, compressors
- Located in `profiles/`: `yutaki_s.py`, `yutaki_s80.py`, `yutaki_m.py`, etc.
- Base class: `HitachiHeatPumpProfile` with detection logic

### COP Calculation
- Coefficient of Performance monitoring with quality indicators
- Uses energy accumulation over time for accuracy
- Supports both internal and external temperature sensors
- Quality levels: `no_data`, `insufficient_data`, `preliminary`, `optimal`
- Located in `domain/services/cop.py`

### Thermal Energy Tracking
- **Separate** tracking for heating and cooling
- Real-time power: `thermal_power_heating`, `thermal_power_cooling`
- Daily energy: auto-resets at midnight
- Total energy: persistent across HA restarts
- **Defrost filtering**: excludes defrost cycles from measurements
- **Post-cycle lock**: prevents counting thermal inertia noise after compressor stops
- Located in `domain/services/thermal/`

### Devices Created
The integration creates multiple HA devices based on configuration:
- **ATW-MBS-02 Gateway**: connectivity monitoring
- **Control Unit**: main heat pump control and sensors
- **Primary Compressor**: always present
- **Secondary Compressor**: S80 model only
- **Circuit 1 & 2**: heating/cooling zones (climate entities)
- **DHW**: domestic hot water (water_heater entity)
- **Pool**: pool heating (if configured)

## Important Development Notes

### When Adding New Entities

1. Determine the **business domain** (not entity type)
2. Add to appropriate `entities/<domain>/` folder
3. Create builder function following the pattern
4. Update platform orchestrator file to call builder
5. **Never** add business logic to entity classes - use domain services

### When Modifying Calculations

1. Business logic changes go in `domain/services/`
2. Adapter changes go in `adapters/calculators/`
3. Test domain services in isolation (no HA mocks needed)
4. Domain layer must remain HA-agnostic

### Modbus Register Access
- Registers defined in `api/modbus/registers/atw_mbs_02.py`
- Accessed via coordinator: `coordinator.data["register_key"]`
- Gateway type info in `api/GATEWAY_INFO`
- **CONTROL vs STATUS registers**: The ATW-MBS-02 gateway exposes two register ranges:
  - **CONTROL** (R/W): commands sent to the heat pump
  - **STATUS** (R): actual state read from the heat pump
  - **Always read from STATUS registers** for sensor entities — reading CONTROL registers only reflects what was commanded, not the actual running state

### Circuit Climate Architecture
- **Operating mode is global**: register 1001 (`unit_mode`) controls heat/cool/auto for **all** circuits simultaneously
- **Circuit power is per-circuit**: registers 1002 (circuit 1) and 1013 (circuit 2) toggle each circuit independently
- **Single circuit active**: climate entity exposes `off`/`heat`/`cool`/`auto` and controls both power and global mode
- **Two circuits active**: climate entities expose only `off`/`heat_cool` (power toggle only) — global mode is controlled exclusively via the `control_unit_operation_mode` select entity to avoid unintended side-effects between circuits

### Entity Migration (v2.0.0)
- `entity_migration.py` handles unique_id migrations for beta users
- Runs automatically during integration setup
- Migration tracking in `2.0.0_entity_migration*.md` files

## Code Quality Standards

- **Linting**: Ruff with Home Assistant ruleset (see `.ruff.toml`)
- **Type hints**: Required for all function signatures
- **Docstrings**: Required for all public functions/classes
- **Line length**: Enforced by formatter, not limited
- **Import conventions**: Use aliases from `.ruff.toml` (e.g., `vol`, `cv`, `dt_util`)

## Testing

Tests are in `tests/` directory:
- `tests/domain/`: Domain layer unit tests (pure Python, no HA)
- Test files use `pytest` and `pytest-asyncio`

Run tests: `uv run pytest`

## Dependencies

All dependencies are declared in `pyproject.toml` (single source of truth).

**Runtime**:
- `pymodbus>=3.6.9,<4.0.0` (Modbus communication)
- Home Assistant core

**Development** (via `[dependency-groups] dev`):
- `pytest-homeassistant-custom-component` (pulls HA as transitive dep)
- `ruff==0.13.3` (linting/formatting)
- `pre-commit>=4.3.0` (git hooks)
- `pytest`, `pytest-asyncio` (testing)

## Branch Strategy

- **Main branch**: `dev` (target for PRs)
- **Current work**: `beta/2.0.0` (major architecture refactor)
- Feature branches should be created from `dev`

## Git Conventions

- **No AI signature**: Do not add "Co-Authored-By: Claude..." in commit messages
- Follow conventional commit format when appropriate

## Documentation

- **README.md**: User-facing documentation
- **documentation/architecture.md**: Detailed French architecture docs
- **documentation/entities.md**: Entity organization patterns
- **domain/README.md**: Domain layer specifics
- **adapters/README.md**: Adapter layer specifics
- **entities/README.md**: Entity layer specifics
- Each `entities/<domain>/` has focused README files

## Common Patterns

### Accessing Heat Pump Data
```python
# Via coordinator
value = coordinator.data.get("register_key")

# Check if feature exists (requires both circuit_id AND mode)
if coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING):
    # ...

if coordinator.profile.supports_dhw:
    # ...
```

### Creating Domain-Based Entities
```python
# Avoid: Creating entities directly in platform files
# Do: Use domain builders

# In entities/mydomain/sensors.py
def build_mydomain_sensors(coordinator, entry_id):
    descriptions = [
        HitachiYutakiSensorEntityDescription(
            key="my_sensor",
            translation_key="my_sensor",
            device_type=DEVICE_CONTROL_UNIT,
            # ...
        )
    ]
    from ..base.sensor import _create_sensors
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_CONTROL_UNIT)

# In sensor.py
entities.extend(build_mydomain_sensors(coordinator, entry.entry_id))
```

### Using Domain Services
```python
# Inject dependencies via adapters
electrical_calc = ElectricalPowerCalculatorAdapter(hass, entry, power_supply)
thermal_calc = thermal_power_calculator_wrapper
storage = InMemoryStorage(max_len=100)
accumulator = EnergyAccumulator(storage, threshold_seconds=180)

# Create service
cop_service = COPService(accumulator, thermal_calc, electrical_calc)

# Use in entity
cop_value = cop_service.get_value()
```

## Version Management

Version is defined in two files (kept in sync by `make bump`):
- `manifest.json`: `"version"` — **source of truth** (read by HA core + HACS at runtime)
- `pyproject.toml`: `version` — metadata only (uv/build tools)

Use `make bump` to increment the last numeric segment and update both files automatically.
