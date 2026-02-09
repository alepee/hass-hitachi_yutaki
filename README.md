[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

# Hitachi air-to-water heat pumps Integration for Home Assistant

This custom integration allows you to control and monitor your Hitachi **Yutaki** and **Yutampo** air-to-water heat pumps through Home Assistant using a Modbus ATW-MBS-02 gateway.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alepee&category=integration&repository=hass-hitachi_yutaki)

## Compatibility

- **Compatible Models**: 2016 and newer Hitachi air-to-water heat pumps
- **Tested With**: Yutaki S80, Yutaki S, Yutaki S Combi, Yutampo R32
- **Required Hardware**: ATW-MBS-02 Modbus gateway

> **Important**: Models manufactured before 2016 use different Modbus registers and are not compatible. If you do have an older Heat Pump already equiped with a Modbus gateway, you can [open an issue](https://github.com/alepee/hass-hitachi_yutaki/issues/new?title=Pre-2016%20Heat%20Pump%20support%20request) if your have time to help me add support for your model.

## Features

The integration provides:
- Automatic model detection and configuration
- Resilient to gateway connection issues at startup
- Gateway synchronization status monitoring with automated repair suggestions
- Multi-language support (English, French)
- Real-time performance monitoring (COP calculation)
- Comprehensive alarm descriptions with translations
- Advanced configuration options:
  - Single/Three phase power supply support
  - Real-time voltage monitoring (optional)
  - External energy meter support (optional)
  - External water temperature sensors (optional)
  - Customizable scan intervals
  - Developer mode for testing
- Multiple device support:
  - Main control unit
  - Primary compressor
  - Secondary compressor (S80)
  - Up to 2 heating/cooling circuits
  - Domestic hot water
  - Swimming pool
- Outdoor Temperature Compensation (OTC) support
- Energy saving features (ECO mode)
- Smart grid integration

The integration automatically detects your heat pump model and available features. It creates several devices based on your system configuration:

### ATW-MBS-02 Gateway Device

| Entity | Type | Description | Category |
|--------|------|-------------|----------|
| connectivity | binary_sensor | Indicates if the gateway is connected and responding | diagnostic |
| system_state | sensor | Gateway synchronization state with the heat pump | diagnostic |

### Heat Pump Control Unit Device

#### Controls

| Entity | Type | Description | Values |
|--------|------|-------------|--------|
| power | switch | Main power switch for the heat pump unit | on/off |
| operation_mode | select | Operating mode of the heat pump (modes depend on configuration) | heat only, or heat/cool/auto |

#### Temperatures

| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| outdoor_temp | sensor | Outdoor ambient temperature measurement | °C |
| water_inlet_temp | sensor | Water temperature at the heat pump inlet | °C |
| water_outlet_temp | sensor | Water temperature at the heat pump outlet | °C |
| water_target_temp | sensor | Corrected target water temperature | °C |

#### System Status

| Entity | Type | Description | Category |
|--------|------|-------------|----------|
| operation_state | sensor | Current operation state with detailed description | diagnostic |
| alarm | sensor | Current alarm status | diagnostic |
| defrost | binary_sensor | Unit is currently in defrost mode | diagnostic |
| compressor | binary_sensor | Compressor is running | diagnostic |
| boiler | binary_sensor | Backup boiler is active (if supported) | diagnostic |
| dhw_heater | binary_sensor | DHW electric heater is active (if DHW configured) | diagnostic |
| solar | binary_sensor | Solar system is active (disabled by default) | diagnostic |
| space_heater | binary_sensor | Space heating electric heater is active (disabled by default) | diagnostic |
| smart_function | binary_sensor | Smart grid function is active (disabled by default) | diagnostic |

#### Hydraulic

| Entity | Type | Description | Unit | Category |
|--------|------|-------------|------|----------|
| water_flow | sensor | Current water flow rate through the system | m³/h | diagnostic |
| pump_speed | sensor | Current speed of the water circulation pump | % | diagnostic |
| pump1 | binary_sensor | Water pump 1 is running (disabled by default) | - | diagnostic |
| pump2 | binary_sensor | Water pump 2 is running (disabled by default) | - | diagnostic |
| pump3 | binary_sensor | Water pump 3 is running (disabled by default) | - | diagnostic |

#### Electrical Energy

| Entity | Type | Description | Unit | Category |
|--------|------|-------------|------|----------|
| power_consumption | sensor | Total electrical energy consumed by the unit | kWh | diagnostic |

#### Thermal Energy

| Entity | Type | Description | Unit | Category |
|--------|------|-------------|------|----------|
| thermal_power_heating | sensor | Real-time thermal heating power output | kW | diagnostic |
| thermal_power_cooling | sensor | Real-time thermal cooling power output (cooling circuits only) | kW | diagnostic |
| thermal_energy_heating_daily | sensor | Daily thermal heating energy (resets at midnight) | kWh | diagnostic |
| thermal_energy_heating_total | sensor | Total cumulative thermal heating energy | kWh | diagnostic |
| thermal_energy_cooling_daily | sensor | Daily thermal cooling energy (cooling circuits only) | kWh | diagnostic |
| thermal_energy_cooling_total | sensor | Total cumulative thermal cooling energy (cooling circuits only) | kWh | diagnostic |

#### Performance (COP)

| Entity | Type | Description | Category |
|--------|------|-------------|----------|
| cop_heating | sensor | Space heating COP (water flow, temperatures, electrical consumption) | diagnostic |
| cop_cooling | sensor | Space cooling COP (cooling circuits only) | diagnostic |
| cop_dhw | sensor | Domestic hot water COP (if DHW configured) | diagnostic |
| cop_pool | sensor | Pool heating COP (if pool configured) | diagnostic |

### Primary Compressor Device

| Entity | Type | Description | Unit | Category |
|--------|------|-------------|------|----------|
| compressor_running | binary_sensor | Compressor is running | - | diagnostic |
| compressor_frequency | sensor | Operating frequency | Hz | diagnostic |
| compressor_current | sensor | Electrical current draw | A | diagnostic |
| compressor_tg_gas_temp | sensor | Gas temperature | °C | diagnostic |
| compressor_ti_liquid_temp | sensor | Liquid temperature | °C | diagnostic |
| compressor_td_discharge_temp | sensor | Discharge temperature | °C | diagnostic |
| compressor_te_evaporator_temp | sensor | Evaporator temperature | °C | diagnostic |
| compressor_evi_indoor_expansion_valve_opening | sensor | Indoor expansion valve opening | % | diagnostic |
| compressor_evo_outdoor_expansion_valve_opening | sensor | Outdoor expansion valve opening | % | diagnostic |
| compressor_cycle_time | sensor | Average time between compressor starts | min | diagnostic |
| compressor_runtime | sensor | Compressor runtime | min | diagnostic |
| compressor_resttime | sensor | Compressor rest time | min | diagnostic |

### Secondary Compressor Device (S80 Model Only)

| Entity | Type | Description | Unit | Category |
|--------|------|-------------|------|----------|
| secondary_compressor_running | binary_sensor | Secondary compressor is running | - | diagnostic |
| secondary_compressor_frequency | sensor | Operating frequency | Hz | diagnostic |
| secondary_compressor_current | sensor | Electrical current draw | A | diagnostic |
| secondary_compressor_discharge_temp | sensor | Discharge temperature | °C | diagnostic |
| secondary_compressor_suction_temp | sensor | Suction temperature | °C | diagnostic |
| secondary_compressor_discharge_pressure | sensor | Discharge pressure | bar | diagnostic |
| secondary_compressor_suction_pressure | sensor | Suction pressure | bar | diagnostic |
| secondary_compressor_cycle_time | sensor | Average time between compressor starts | min | diagnostic |
| secondary_compressor_runtime | sensor | Compressor runtime | min | diagnostic |
| secondary_compressor_resttime | sensor | Compressor rest time | min | diagnostic |

### Circuit Device (up to 2 circuits)

Each circuit creates a climate entity with HVAC modes that depend on the system configuration:
- **Single circuit**: Exposes `off` / `heat` / `cool` / `auto` modes with direct global mode control
- **Two circuits**: Exposes `off` / `heat_cool` (power toggle only) — global mode is controlled via the Control Unit's `operation_mode` select to avoid conflicts between circuits

#### Climate & Controls

| Entity | Type | Description | Values |
|--------|------|-------------|--------|
| climate | climate | Main climate control entity | off/heat/cool/auto or off/heat_cool |
| eco_mode | switch | Enable ECO mode (reduced temperatures) | on/off |
| thermostat | switch | Enable Modbus thermostat function (if available) | on/off |

#### Configuration (disabled by default)

| Entity | Type | Description | Values/Unit | Category |
|--------|------|-------------|-------------|----------|
| otc_calculation_method_heating | select | Heating water temperature calculation method | disabled/points/gradient/fix | config |
| otc_calculation_method_cooling | select | Cooling water temperature calculation method | disabled/points/fix | config |
| max_flow_temp_heating_otc | number | Maximum heating water temperature for OTC | °C (0-80) | config |
| max_flow_temp_cooling_otc | number | Maximum cooling water temperature for OTC | °C (0-80) | config |
| heat_eco_offset | number | Temperature offset in ECO mode for heating | °C (1-10) | config |
| cool_eco_offset | number | Temperature offset in ECO mode for cooling | °C (1-10) | config |

#### Service

| Service | Description | Fields |
|---------|-------------|--------|
| `hitachi_yutaki.set_room_temperature` | Set the room temperature for a circuit | `temperature` (0-50°C, step 0.1) |

### Domestic Hot Water Device (if configured)

| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| dhw | water_heater | Main DHW control entity | off/standard/high demand, 30-60°C |
| boost | switch | Temporarily boost DHW production | on/off |
| antilegionella | button | Manually start a high temperature anti-legionella cycle | - |
| antilegionella_temp | number | Target temperature for anti-legionella treatment (disabled by default) | °C (60-80) |
| antilegionella_cycle | binary_sensor | Anti-legionella cycle is currently running | on/off |

### Swimming Pool Device (if configured)

| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | Power switch for swimming pool heating | on/off |
| pool_target_temp | number | Target temperature for swimming pool water | °C (0-80) |
| pool_current_temp | sensor | Current pool water temperature | °C |

## Installation

### HACS Installation (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alepee&repository=hass-hitachi_yutaki)

1. Add this repository to HACS:
    - Open HACS in Home Assistant
    - Click on "Integrations"
    - Click the three dots in the top right corner
    - Select "Custom repositories"
    - Add the repository URL: `https://github.com/alepee/hass-hitachi_yutaki`
    - Select category: "Integration"
    - Click "Add"

2. Install the integration through HACS:
    - Click on "Integrations"
    - Search for "Hitachi Yutaki"
    - Click "Download"
    - Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/hitachi_yutaki` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Removal

1. Go to **Settings** > **Devices & Services**
2. Find the **Hitachi Heat Pump** integration
3. Click the three dots menu and select **Delete**
4. Restart Home Assistant
5. If installed via HACS, you can also remove the integration files through HACS > Integrations > Hitachi Yutaki > Remove

## Configuration

> **Note:** The heat pump's central control mode must NOT be set to 'Local' (0). Accepted modes are: Air (1), Water (2), or Total (3). **The 'Air' (1) mode is recommended for most installations.** Please check this setting in your heat pump parameters (System Configuration > General Options > External Control Option > Control Mode).

The configuration flow guides you through several steps:

1. **Gateway selection**: Choose your gateway type (ATW-MBS-02)
2. **Gateway configuration**: Enter connection details
    - Name (optional)
    - Modbus gateway IP address
    - Port (default: 502)
    - Modbus slave ID (default: 1)
3. **Profile selection**: Choose your heat pump model (or let the integration auto-detect)
4. **Sensors & power**: Configure optional sensors
    - Power supply type (single phase/three phase)
    - Voltage entity (optional - for real-time voltage measurements)
    - Energy meter entity (optional - for real-time power measurements)
    - Water inlet temperature entity (optional - for more accurate COP and thermal energy calculations)
    - Water outlet temperature entity (optional - for more accurate COP and thermal energy calculations)
5. **Advanced settings** (optional):
    - Scan interval (seconds)
    - Developer mode (enables all entities regardless of heat pump configuration)

### Reconfiguration

You can reconfigure the integration at any time via **Settings** > **Devices & Services** > **Hitachi Heat Pump** > **Configure**. This allows you to change the gateway type, connection settings, heat pump profile, and optional sensors without removing and re-adding the integration.

## COP Calculation Methods

The integration provides advanced COP (Coefficient of Performance) monitoring with quality indicators and multiple calculation methods:

### Quality Indicators

Each COP measurement includes a quality indicator to help assess its reliability:
- `no_data`: No measurements available
- `insufficient_data`: Too few measurements for reliable calculation (< 6 measurements or < 3 minutes)
- `preliminary`: Basic reliability achieved (6-10 measurements or 3-15 minutes)
- `optimal`: High reliability achieved (≥ 10 measurements and ≥ 15 minutes)

### Using External Temperature Sensors

When both water inlet and outlet temperature entities are configured:
- Uses more precise external temperature measurements
- Calculates COP using energy accumulation over time
- Updates every 30 seconds
- Provides quality indicators for measurement reliability
- Best option when you have accurate external temperature sensors

### Using Internal Temperature Sensors

When no external temperature entities are configured:
- Uses the heat pump's internal temperature sensors
- Accumulates thermal and electrical energy over time
- Calculates COP from accumulated energy values
- Helps mitigate the impact of temperature measurement precision (1°C)
- Default method using built-in sensors

### Additional Attributes

Each COP sensor provides additional attributes:
- `quality`: Current quality level of the measurement
- `measurements`: Number of measurements used in calculation
- `time_span_minutes`: Time span covered by the measurements

## Thermal Energy Monitoring

The integration provides detailed thermal energy monitoring with **separate tracking for heating and cooling**:

### Real-time Power Output

Two sensors show instantaneous thermal power:
- `thermal_power_heating`: Heating power (when ΔT > 0) in kW
- `thermal_power_cooling`: Cooling power (when ΔT < 0) in kW - only for units with cooling circuits

Power is calculated from:
- Water flow rate (m³/h)
- Temperature difference between outlet and inlet (ΔT in °C)
- Water specific heat capacity (4.185 kJ/kg·K)

### Daily Energy Production

Sensors track energy produced since midnight (auto-reset):
- `thermal_energy_heating_daily`: Heating energy (kWh)
- `thermal_energy_cooling_daily`: Cooling energy (kWh) - cooling circuits only

Features:
- Automatic state restoration after Home Assistant restart (same day only)
- Independent counters for heating and cooling

### Total Energy Production

Sensors maintain running totals:
- `thermal_energy_heating_total`: Total heating energy (kWh)
- `thermal_energy_cooling_total`: Total cooling energy (kWh) - cooling circuits only

Features:
- Persistent state across Home Assistant restarts
- Long-term performance tracking

### Measurement Logic

**What is measured:**
- Only energy **produced by the heat pump** (not auxiliary sources)
- Heating: Water temperature increase (ΔT > 0) → circuits, DHW, pool
- Cooling: Water temperature decrease (ΔT < 0) → cooling circuits

**Filtering applied:**
- **Defrost mode** (`is_defrosting == True`): No measurement (prevents false cooling energy)
- **Cooling mode**: Only counted when compressor is running
- **Heating mode with post-cycle lock**:
  - Thermal inertia energy is counted after compressor stops (while ΔT > 0)
  - Lock activates when ΔT drops to zero to prevent counting noise/fluctuations
  - Lock releases when compressor restarts
- This ensures accurate COP calculations (Thermal Energy / Electrical Energy)

### Migration from v1.x

In v2.0.0, the following sensors have been **replaced** (old entities are automatically migrated to new unique_ids):
- `thermal_power` → `thermal_power_heating`
- `daily_thermal_energy` → `thermal_energy_heating_daily`
- `total_thermal_energy` → `thermal_energy_heating_total`

**Why this change?** The old sensors counted defrost cycles as energy production, resulting in unrealistic COP values (e.g., COP > 8). The new sensors correctly separate heating from cooling and filter defrost periods.

## Known Limitations

- **Modbus TCP only**: The integration communicates via Modbus TCP over the ATW-MBS-02 gateway. Direct serial Modbus is not supported.
- **Pre-2016 models**: Older Hitachi heat pumps use different Modbus register maps and are not compatible.
- **Temperature precision**: Internal temperature sensors have 1°C precision. For more accurate COP calculations, configure external temperature sensors with higher resolution.
- **Single gateway**: Each integration instance connects to one gateway. Multiple gateways require multiple integration instances.
- **Global operating mode**: The heat/cool/auto mode is a global setting shared across all circuits. When two circuits are active, the mode can only be changed via the Control Unit's operation_mode select.
- **No automatic discovery**: The gateway must be configured manually (IP address and port).

## Troubleshooting

### Gateway cannot connect

- Verify the ATW-MBS-02 gateway is powered on and connected to your network
- Check the IP address and port (default: 502) in the integration configuration
- Ensure no other Modbus client is connected to the gateway (only one connection is supported)
- Verify the Modbus slave ID matches your gateway configuration (default: 1)

### Gateway shows "Desynchronized" state

The gateway has lost synchronization with the heat pump. The integration creates a repair issue with guidance. Common causes:
- Heat pump power interruption
- Gateway firmware issue
- Communication cable problem between gateway and heat pump

### Entities show "Unavailable"

- Check the gateway connectivity sensor — if it shows disconnected, see "Gateway cannot connect"
- The integration automatically recovers when the gateway comes back online
- After a Home Assistant restart, entities may briefly show unavailable while the connection is re-established

### COP values seem inaccurate

- Check the `quality` attribute of the COP sensor — `preliminary` or `optimal` quality is needed for reliable values
- Configure external water temperature sensors for better precision (internal sensors have 1°C resolution)
- COP is filtered during defrost cycles and post-compressor shutdown to avoid false readings
- COP sensors track heating and DHW separately — ensure you're reading the right sensor for the operating mode

### Heat pump control mode

The heat pump's external control mode must NOT be set to 'Local' (0). Set it to Air (1), Water (2), or Total (3) via: **System Configuration** > **General Options** > **External Control Option** > **Control Mode**.

## Development

### Architecture

This integration follows the **Hexagonal Architecture** (Ports and Adapters) pattern, providing clear separation of concerns and improved maintainability:

- **Domain Layer** (`domain/`): Pure business logic with zero Home Assistant dependencies
  - `models/`: Data structures (COPInput, ThermalEnergyResult, PowerMeasurement, etc.)
  - `ports/`: Abstract interfaces (Storage, DataProvider, StateProvider, Calculators)
  - `services/`: Business logic services (COPService, ThermalPowerService, DefrostGuard, CompressorTimingService)

- **Adapters Layer** (`adapters/`): Concrete implementations bridging domain with Home Assistant
  - `calculators/`: Electrical and thermal power calculation adapters
  - `providers/`: Data providers from HA coordinator and entity states
  - `storage/`: Storage implementations (in-memory, Recorder rehydration)

- **Entity Layer** (`entities/`): Domain-driven entity organization using domain services through adapters

**Benefits:**
- **Testability**: Domain layer is 100% testable without Home Assistant mocks
- **Reusability**: COP and thermal logic can be shared across sensor, climate, and water_heater entities
- **Maintainability**: Business logic centralized in domain layer, single point of truth for calculations
- **Extensibility**: Easy to add new entity types or change storage implementations

### Architecture Documentation

For detailed information about each architectural layer, see the specialized README files:

- **[Domain Layer](custom_components/hitachi_yutaki/domain/README.md)**: Pure business logic with zero Home Assistant dependencies
- **[Adapters Layer](custom_components/hitachi_yutaki/adapters/README.md)**: Concrete implementations bridging domain with Home Assistant
- **[Entities Layer](custom_components/hitachi_yutaki/entities/README.md)**: Domain-driven entity organization

### Project Structure

```
hitachi_yutaki/
├── .github/
│   └── workflows/              # CI/CD workflows
├── custom_components/
│   └── hitachi_yutaki/
│       ├── domain/             # Pure business logic (hexagonal architecture)
│       │   ├── models/         # Data structures (COPInput, ThermalEnergyResult, etc.)
│       │   ├── ports/          # Abstract interfaces (Storage, DataProvider, etc.)
│       │   └── services/       # Business logic services
│       │       └── thermal/    # Thermal power and energy calculation
│       ├── adapters/           # Concrete implementations (hexagonal architecture)
│       │   ├── calculators/    # Power calculation adapters
│       │   ├── providers/      # Data providers from HA coordinator/entities
│       │   └── storage/        # Storage implementations (in-memory, Recorder)
│       ├── entities/           # Domain-driven entity organization
│       │   ├── base/           # Base entity classes for all platforms
│       │   ├── circuit/        # Circuit climate, switches, selects, numbers
│       │   ├── compressor/     # Compressor sensors and binary sensors
│       │   ├── control_unit/   # Control unit sensors, selects, switches
│       │   ├── dhw/            # Domestic Hot Water entities
│       │   ├── gateway/        # Gateway connectivity sensors
│       │   ├── hydraulic/      # Water flow, pumps, temperature sensors
│       │   ├── performance/    # COP sensors
│       │   ├── pool/           # Pool heating entities
│       │   ├── power/          # Electrical power sensors
│       │   └── thermal/        # Thermal energy sensors
│       ├── api/                # Modbus communication layer
│       │   └── modbus/
│       │       └── registers/  # Register definitions (ATW-MBS-02)
│       ├── profiles/           # Heat pump model profiles
│       ├── translations/       # Language files (en.json, fr.json)
│       ├── __init__.py         # Integration setup, migration, device registration
│       ├── config_flow.py      # Multi-step configuration flow
│       ├── coordinator.py      # Data update coordinator
│       ├── entity_migration.py # Entity unique_id migration (v1.x → v2.0)
│       ├── repairs.py          # HA Repairs integration
│       ├── services.yaml       # Service definitions
│       ├── sensor.py           # Sensor platform orchestrator
│       ├── binary_sensor.py    # Binary sensor platform orchestrator
│       ├── climate.py          # Climate platform orchestrator
│       ├── water_heater.py     # Water heater platform orchestrator
│       ├── switch.py           # Switch platform orchestrator
│       ├── select.py           # Select platform orchestrator
│       ├── number.py           # Number platform orchestrator
│       ├── button.py           # Button platform orchestrator
│       ├── const.py            # Constants
│       └── manifest.json       # Integration manifest
├── scripts/                    # Development scripts
├── tests/                      # Test files
│   ├── domain/                 # Domain layer unit tests (pure Python)
│   │   └── services/
│   │       └── thermal/        # Thermal service tests
│   ├── profiles/               # Profile detection tests
│   ├── test_entity_migration.py
│   └── test_modbus_api.py
└── documentation/              # Architecture and investigation docs
```

### Setting Up Development Environment

#### Option 1: Using Dev Container (Recommended)
This repository includes a dev container configuration, which provides a fully configured development environment. To use it:

1. Install [Visual Studio Code](https://code.visualstudio.com/) and the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Clone this repository
3. Open the repository in VS Code
4. When prompted to "Reopen in Container", click "Yes"
   - Or click F1, type "Dev Containers: Rebuild and Reopen in Container"

The container includes:
- All required development dependencies
- Pre-configured development tools
- Pre-commit hooks
- A ready-to-use Home Assistant development instance

#### Option 2: Manual Setup

1. Clone the repository:
```bash
git clone https://github.com/alepee/hass-hitachi_yutaki.git
cd hitachi_yutaki
```

2. Set up the development environment:
```bash
make setup
```

3. Start Home Assistant in development mode:
```bash
make ha-run
```

Home Assistant will be available at `http://localhost:8123`. To use a custom port, add the following to `config/configuration.yaml`:
```yaml
http:
  server_port: 9125
```

Available `make` targets (run `make help` to list all):

| Target | Description |
|--------|-------------|
| `make install` | Install all dependencies (dev included) |
| `make setup` | Full project setup (deps + pre-commit hooks) |
| `make lint` | Run ruff linter with auto-fix |
| `make format` | Run ruff formatter |
| `make check` | Run all code quality checks (lint + format) |
| `make test` | Run all tests |
| `make test-domain` | Run domain layer tests only (pure Python, no HA) |
| `make test-coverage` | Run tests with coverage report |
| `make ha-run` | Start a local HA dev instance with debug config |
| `make ha-upgrade` | Upgrade HA to latest release |
| `make ha-dev-branch` | Install HA from dev branch (bleeding edge) |
| `make ha-version` | Install a specific HA version (interactive) |
| `make bump` | Bump version (last numeric segment) |
| `make version` | Show current version |

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality. They are automatically installed when you set up the development environment, but you can also install them manually:

```bash
pre-commit install
```

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Write tests for your changes
4. Ensure all tests pass and pre-commit hooks are satisfied
5. Submit a pull request

## License

This project is under the MIT License. See the LICENSE file for details.

## Credits

This integration was developed by Antoine Lépée and is not affiliated with Hitachi Ltd.

## Support

For bugs and feature requests, please use the [GitHub issues](https://github.com/alepee/hass-hitachi_yutaki/issues) page.
