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

| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| connectivity | binary_sensor | Indicates if the gateway is connected and responding | - |
| sync_state   | sensor        | Indicates the gateway synchronization state with the heat pump | - |

### Heat Pump Control Unit Device

#### Controls
| Entity | Type | Description | Values/Unit | Category |
|--------|------|-------------|-------------|----------|
| power | switch | Main power switch for the heat pump unit | on/off | - |
| operation_mode | select | Operating mode of the heat pump (modes depend on configuration) | heat only or heat/cool/auto | - |

#### Temperatures
| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| outdoor_temp | sensor | Outdoor ambient temperature measurement | °C |
| water_inlet_temp | sensor | Water temperature at the heat pump inlet | °C |
| water_outlet_temp | sensor | Water temperature at the heat pump outlet | °C |
| water_target_temp | sensor | Corrected target water temperature | °C |

#### System Status
| Entity | Type | Description | Values |
|--------|------|-------------|---------|
| operation_state | sensor | Current operation state with detailed description | - |
| alarm | sensor | Current alarm status | - |
| defrost | binary_sensor | Indicates if the unit is currently in defrost mode | on/off |
| solar | binary_sensor | Indicates if the solar system is active | on/off |
| pump1 | binary_sensor | Indicates if water pump 1 is running | on/off |
| pump2 | binary_sensor | Indicates if water pump 2 is running | on/off |
| pump3 | binary_sensor | Indicates if water pump 3 is running | on/off |
| compressor | binary_sensor | Indicates if the compressor is running | on/off |
| boiler | binary_sensor | Indicates if the backup boiler is active | on/off |
| dhw_heater | binary_sensor | Indicates if the DHW electric heater is active | on/off |
| space_heater | binary_sensor | Indicates if the space heating electric heater is active | on/off |
| smart_function | binary_sensor | Indicates if the smart grid function is active | on/off |

#### Performance Metrics
| Entity | Type | Description | Unit | Category |
|--------|------|-------------|------|----------|
| water_flow | sensor | Current water flow rate through the system | m³/h | diagnostic |
| pump_speed | sensor | Current speed of the water circulation pump | % | diagnostic |
| compressor_frequency | sensor | Current operating frequency of the compressor | Hz | diagnostic |
| compressor_current | sensor | Current electrical consumption of the compressor | A | diagnostic |
| compressor_cycle_time | sensor | Average time between compressor starts | min | diagnostic |
| power_consumption | sensor | Total electrical energy consumed by the unit | kWh | diagnostic |
| thermal_power | sensor | Real-time thermal power output | kW | diagnostic |
| daily_thermal_energy | sensor | Daily thermal energy production (resets at midnight) | kWh | diagnostic |
| total_thermal_energy | sensor | Total cumulative thermal energy production | kWh | diagnostic |
| cop_heating | sensor | Space heating COP calculated from water flow, temperatures and electrical consumption | - | diagnostic |
| cop_cooling | sensor | Space cooling COP calculated from water flow, temperatures and electrical consumption | - | diagnostic |
| cop_dhw | sensor | Domestic hot water COP calculated from water flow, temperatures and electrical consumption | - | diagnostic |
| cop_pool | sensor | Pool heating COP calculated from water flow, temperatures and electrical consumption | - | diagnostic |

### Primary Compressor Device

| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| compressor_frequency | sensor | Operating frequency | Hz |
| compressor_current | sensor | Electrical current draw | A |
| compressor_tg_gas_temp | sensor | Gas temperature | °C |
| compressor_ti_liquid_temp | sensor | Liquid temperature | °C |
| compressor_td_discharge_temp | sensor | Discharge temperature | °C |
| compressor_te_evaporator_temp | sensor | Evaporator temperature | °C |
| compressor_evi_indoor_expansion_valve_opening | sensor | Indoor expansion valve opening | % |
| compressor_evo_outdoor_expansion_valve_opening | sensor | Outdoor expansion valve opening | % |

### Secondary Compressor Device (S80 Model Only)

| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| secondary_compressor_discharge_temp | sensor | Discharge temperature | °C |
| secondary_compressor_suction_temp | sensor | Suction temperature | °C |
| secondary_compressor_discharge_pressure | sensor | Discharge pressure | mbar |
| secondary_compressor_suction_pressure | sensor | Suction pressure | mbar |
| secondary_compressor_frequency | sensor | Operating frequency | Hz |
| secondary_compressor_current | sensor | Electrical current draw | A |
| secondary_compressor_cycle_time | sensor | Average time between compressor starts | min |
| secondary_compressor_runtime | sensor | Compressor runtime | min |
| secondary_compressor_resttime | sensor | Compressor rest time | min |

### Climate Device (up to 2 circuits)

#### Controls
| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | Power switch for the circuit | on/off |
| operation_mode | select | Operating mode selection | heat/cool/auto |
| preset_mode | select | Energy saving mode selection | comfort/eco |
| hvac_action | sensor | Current operation status | off/idle/heating/cooling/defrost |

#### Configuration
| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| otc_calculation_method_heating | select | Method used for heating water temperature calculation | disabled/points/gradient/fix |
| otc_calculation_method_cooling | select | Method used for cooling water temperature calculation | disabled/points/fix |
| max_flow_temp_heating_otc | number | Maximum heating water temperature for OTC | °C (0-80) |
| max_flow_temp_cooling_otc | number | Maximum cooling water temperature for OTC | °C (0-80) |
| heat_eco_offset | number | Temperature offset in ECO mode for heating | °C (1-10) |
| cool_eco_offset | number | Temperature offset in ECO mode for cooling | °C (1-10) |
| thermostat | switch | Enable/disable Modbus thermostat function | on/off |

### Domestic Hot Water Device (if configured)

| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| dhw | water_heater | Main DHW control entity | - |
| boost | switch | Temporarily boost DHW production | on/off |
| antilegionella_temperature | number | Target temperature for anti-legionella treatment | °C (60-80) |
| antilegionella_cycle | binary_sensor | Indicates if an anti-legionella cycle is currently running | on/off |
| antilegionella | button | Manually start a high temperature anti-legionella treatment cycle | - |

The main DHW control entity (`water_heater`) provides:
- Power control (on/off)
- Operation modes (off, standard, high demand)
- Temperature control (30-60°C)
- Current temperature display

Additional entities provide granular control over specific features.

### Swimming Pool Device (if configured)

| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | Power switch for swimming pool heating | on/off |
| target_temperature | number | Target temperature for swimming pool water | °C (0-80) |
| current_temperature | sensor | Current pool water temperature | °C |

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

## Configuration

> **Note:** The heat pump's central control mode must NOT be set to 'Local' (0). Accepted modes are: Air (1), Water (2), or Total (3). **The 'Air' (1) mode is recommended for most installations.** Please check this setting in your heat pump parameters (System Configuration > General Options > External Control Option > Control Mode).

1. Go to Settings -> Devices & Services
2. Click "Add Integration"
3. Search for "Hitachi Yutaki"
4. Fill in the required information:
    - Name (optional)
    - Modbus gateway IP address
    - Port (default: 502)
    - Power supply type (single phase/three phase)
    - Voltage entity (optional - for real-time voltage measurements)
    - Power meter entity (optional - for real-time power measurements)
    - Water inlet temperature entity (optional - for more accurate COP and thermal energy calculations)
    - Water outlet temperature entity (optional - for more accurate COP and thermal energy calculations)
    - Advanced settings (optional):
        - Modbus slave ID (default: 1)
        - Scan interval (seconds)
        - Developer mode (enables all entities regardless of heat pump configuration)

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

The integration provides detailed thermal energy monitoring through three complementary sensors:

### Real-time Power Output

The `thermal_power` sensor shows the instantaneous thermal power output in kW, calculated from:
- Water flow rate
- Temperature difference between outlet and inlet (ΔT)
- Water specific heat capacity

Additional attributes provide detailed measurement data:
- `delta_t`: Temperature difference between outlet and inlet (°C)
- `water_flow`: Current water flow rate (m³/h)
- `last_update`: Timestamp of the last measurement

### Daily Energy Production

The `daily_thermal_energy` sensor tracks the thermal energy produced since midnight in kWh. It automatically resets at midnight and provides:
- Automatic state restoration after Home Assistant restart (same day only)
- Average power calculation over the measurement period
- Detailed timing information in attributes:
  - `last_reset`: Last midnight reset timestamp
  - `start_time`: First measurement timestamp of the day
  - `average_power`: Average power over the measurement period (kW)
  - `time_span_hours`: Duration of the measurement period

### Total Energy Production

The `total_thermal_energy` sensor maintains a running total of all thermal energy produced in kWh. It features:
- Persistent state across Home Assistant restarts
- Long-term performance tracking
- Statistical information in attributes:
  - `start_date`: Date of the first measurement
  - `average_power`: Average power since start (kW)
  - `time_span_days`: Number of days since first measurement

### Measurement Accuracy

To ensure accuracy:
- Measurements are only taken when the compressor is running
- Calculations use precise water flow and temperature measurements
- Values are stored with 2 decimal places precision
- All relevant units are clearly indicated in attributes

## Development

### Architecture

This integration follows the **Hexagonal Architecture** (Ports and Adapters) pattern, providing clear separation of concerns and improved maintainability:

- **Domain Layer** (`domain/`): Pure business logic with zero Home Assistant dependencies
  - `models/`: Data structures (COPInput, ThermalEnergyResult, PowerMeasurement, etc.)
  - `ports/`: Abstract interfaces (Storage, DataProvider, StateProvider, Calculators)
  - `services/`: Business logic services (COPService, ThermalPowerService, CompressorTimingService)

- **Adapters Layer** (`adapters/`): Concrete implementations bridging domain with Home Assistant
  - `calculators/`: Electrical and thermal power calculation adapters
  - `providers/`: Data providers from HA coordinator and entity states
  - `storage/`: Storage implementations (in-memory, future persistent storage)

- **Entity Layers** (`sensor/`, `climate/`, `water_heater/`): Home Assistant entities using domain services through adapters

**Benefits:**
- **Testability**: Domain layer is 100% testable without Home Assistant mocks
- **Reusability**: COP and thermal logic can be shared across sensor, climate, and water_heater entities
- **Maintainability**: Business logic centralized in domain layer, single point of truth for calculations
- **Extensibility**: Easy to add new entity types or change storage implementations

### Project Structure

```
hitachi_yutaki/
├── .github/
│   └── workflows/           # CI/CD workflows
├── custom_components/       # The actual integration
│   └── hitachi_yutaki/
│       ├── domain/          # Pure business logic (hexagonal architecture)
│       │   ├── models/       # Data structures (COPInput, ThermalEnergyResult, etc.)
│       │   │   ├── cop.py
│       │   │   ├── electrical.py
│       │   │   ├── thermal.py
│       │   │   └── timing.py
│       │   ├── ports/        # Abstract interfaces (Storage, DataProvider, etc.)
│       │   │   ├── calculators.py
│       │   │   ├── providers.py
│       │   │   └── storage.py
│       │   └── services/     # Business logic services (COP, Thermal, Timing)
│       │       ├── cop.py
│       │       ├── electrical.py
│       │       ├── thermal.py
│       │       └── timing.py
│       ├── adapters/         # Concrete implementations (hexagonal architecture)
│       │   ├── calculators/  # Power calculation adapters
│       │   │   ├── electrical.py
│       │   │   └── thermal.py
│       │   ├── providers/    # Data providers from HA coordinator/entities
│       │   │   ├── coordinator.py
│       │   │   └── entity_state.py
│       │   └── storage/      # Storage implementations
│       │       └── in_memory.py
│       ├── sensor/           # Sensor platform (modularized)
│       │   ├── base.py        # Sensor entity base class
│       │   ├── compressor.py  # Compressor sensors
│       │   ├── diagnostics.py   # System status sensors
│       │   ├── dhw.py        # Domestic hot water sensors
│       │   ├── gateway.py    # Gateway synchronization sensors
│       │   ├── hydraulic.py  # Water temperature/flow sensors
│       │   ├── outdoor.py    # Outdoor temperature sensors
│       │   ├── performance.py # COP sensors
│       │   ├── pool.py       # Pool temperature sensors
│       │   ├── thermal.py    # Thermal energy sensors
│       │   ├── adapters.py   # Backward compatibility re-exports
│       │   └── __init__.py   # Sensor platform setup
│       ├── api/              # API clients (Ports and Adapters)
│       │   ├── base.py
│       │   └── modbus/
│       │       └── registers/
│       │           └── atw_mbs_02.py
│       ├── profiles/         # Heat pump profiles
│       │   ├── base.py
│       │   ├── yutaki_m.py
│       │   ├── yutaki_s.py
│       │   ├── yutaki_s80.py
│       │   ├── yutaki_s_combi.py
│       │   └── yutampo_r32.py
│       ├── translations/     # Language files (en.json, fr.json)
│       ├── __init__.py       # Integration setup
│       ├── binary_sensor.py # Binary sensor platform
│       ├── button.py         # Button platform
│       ├── climate.py        # Climate platform
│       ├── config_flow.py    # Configuration flow
│       ├── const.py          # Constants
│       ├── coordinator.py    # Data update coordinator
│       ├── manifest.json     # Integration manifest
│       ├── number.py         # Number platform
│       ├── select.py         # Select platform
│       ├── switch.py         # Switch platform
│       └── water_heater.py   # Water heater platform
├── scripts/                  # Development scripts
│   ├── dev-branch           # Install dev branch of Home Assistant
│   ├── develop             # Run Home Assistant with debug config
│   ├── lint               # Run code linting
│   ├── setup              # Install development dependencies
│   ├── specific-version   # Install specific HA version
│   └── upgrade            # Upgrade to latest HA version
└── tests/                 # Test files
    └── __init__.py       # Tests package marker
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
chmod +x scripts/setup
./scripts/setup
```

3. Start Home Assistant in development mode:
```bash
./scripts/develop
```

Additional development scripts:
- `./scripts/lint` - Run code linting
- `./scripts/dev-branch` - Install development branch of Home Assistant
- `./scripts/specific-version` - Install specific Home Assistant version
- `./scripts/upgrade` - Upgrade to latest Home Assistant version

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
