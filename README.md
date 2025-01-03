[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

# Hitachi Yutaki Integration for Home Assistant

This custom integration allows you to control and monitor your Hitachi Yutaki heat pump through Home Assistant using a Modbus ATW-MBS-02 gateway.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alepee&repository=hass-hitachi_yutaki)

> ⚠️ **Beta Version - Under Development**
> This integration is currently in active development and should be considered experimental. While it is functional, you may encounter bugs or incomplete features. Use at your own risk and please report any issues you find.
>
> Currently tested only with Yutaki S80 model. Testing with other models is in progress.

## Compatibility

- **Compatible Models**: 2016 and newer Hitachi Yutaki heat pumps
- **Tested With**: Yutaki S80
- **Required Hardware**: ATW-MBS-02 Modbus gateway

> **Important**: Models manufactured before 2016 use different Modbus registers and are not compatible.

## Features

The integration automatically detects your heat pump model and available features. It creates several devices based on your system configuration:

### ATW-MBS-02 Gateway Device

| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| connectivity | binary_sensor | Indicates if the gateway is connected and responding | - |

### Heat Pump Control Unit Device

#### Controls
| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | Main power switch for the heat pump unit | on/off |
| operation_mode | select | Operating mode of the heat pump (heating only or heating/cooling depending on configuration) | cool/heat/auto |

#### Temperatures
| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| outdoor_temp | sensor | Outdoor ambient temperature measurement | °C |
| water_inlet_temp | sensor | Water temperature at the heat pump inlet | °C |
| water_outlet_temp | sensor | Water temperature at the heat pump outlet | °C |

#### System Status
| Entity | Type | Description | Values |
|--------|------|-------------|---------|
| alarm_code | sensor | Current alarm code with description. Provides detailed error descriptions | - |
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
| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| water_flow | sensor | Current water flow rate through the system | m³/h |
| pump_speed | sensor | Current speed of the water circulation pump | % |
| compressor_frequency | sensor | Current operating frequency of the compressor | Hz |
| compressor_current | sensor | Current electrical consumption of the compressor | A |
| compressor_cycle_time | sensor | Average time between compressor starts | min |
| power_consumption | sensor | Total electrical energy consumed by the unit | kWh |

#### R134a Circuit (S80 Model Only)
| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| r134a_discharge_temp | sensor | Temperature of the R134a refrigerant at compressor discharge | °C |
| r134a_suction_temp | sensor | Temperature of the R134a refrigerant at compressor suction | °C |
| r134a_discharge_pressure | sensor | Pressure of the R134a refrigerant at compressor discharge | mbar |
| r134a_suction_pressure | sensor | Pressure of the R134a refrigerant at compressor suction | mbar |
| r134a_compressor_frequency | sensor | Operating frequency of the R134a compressor | Hz |
| r134a_compressor_current | sensor | Electrical current drawn by the R134a compressor | A |

### Climate Device (up to 2 circuits)

#### Controls
| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | Power switch for the circuit | on/off |
| operation_mode | select | Operating mode selection | heat/cool/auto |
| target_temperature | number | Target temperature setpoint | °C (5.0-35.0) |
| current_temperature | sensor | Current measured temperature | °C |
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

Each circuit operates independently and supports:
- Heating mode (if configured)
- Cooling mode (if configured)
- Auto mode (if both heating and cooling are configured)

The operation status (hvac_action) indicates:
- OFF: Circuit is powered off
- IDLE: Circuit is on but not actively heating/cooling
- HEATING: Circuit is actively heating
- COOLING: Circuit is actively cooling
- DEFROST: Unit is in defrost mode

The preset modes affect the target temperature:
- COMFORT: Normal operation
- ECO: Energy-saving operation with temperature offset

### Domestic Hot Water Device (if configured)

| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | Power switch for domestic hot water production | on/off |
| boost | switch | Temporarily boost DHW production | on/off |
| high_demand | switch | Enable high demand mode for increased DHW production | on/off |
| target_temperature | number | Target temperature for domestic hot water | °C (30-80) |
| current_temperature | sensor | Current DHW tank temperature | °C |
| antilegionella | switch | Enable/disable periodic high temperature treatment to prevent legionella | on/off |
| antilegionella_temperature | number | Target temperature for anti-legionella treatment | °C (60-80) |
| electric_heater | binary_sensor | Indicates if the DHW electric heater is active | on/off |

### Swimming Pool Device (if configured)

| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | Power switch for swimming pool heating | on/off |
| temperature | number | Target temperature for swimming pool water | °C (0-80) |

### Primary Compressor Device

| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| compressor_frequency | sensor | Operating frequency | Hz |
| compressor_current | sensor | Electrical current draw | A |

### Secondary Compressor Device (S80 Model Only)

| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| r134a_discharge_temp | sensor | R134a discharge temperature | °C |
| r134a_suction_temp | sensor | R134a suction temperature | °C |
| r134a_discharge_pressure | sensor | R134a discharge pressure | mbar |
| r134a_suction_pressure | sensor | R134a suction pressure | mbar |
| r134a_compressor_frequency | sensor | R134a compressor frequency | Hz |
| r134a_compressor_current | sensor | R134a compressor current | A |

## Installation

### HACS Installation

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

1. Go to Settings -> Devices & Services
2. Click "Add Integration"
3. Search for "Hitachi Yutaki"
4. Fill in the required information:
    - Modbus gateway IP address or serial port
    - Modbus slave ID (default: 1)
    - Port (default: 502 for TCP)
    - Scan interval (seconds)

## Development

### Project Structure

```
hitachi_yutaki/
├── .github/
│   └── workflows/           # CI/CD workflows
├── custom_components/       # The actual integration
│   └── hitachi_yutaki/
├── scripts/                # Development scripts
│   ├── setup_dev.sh       # Linux/Mac setup
│   └── setup_dev.bat      # Windows setup
└── tests/                  # Test files
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
# Linux/MacOS
chmod +x scripts/setup_dev.sh
./scripts/setup_dev.sh

# Windows
scripts\setup_dev.bat
```

3. Run tests:
```bash
pytest
```

4. Run Home Assistant with your development version:
```bash
hass -c config
```

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
