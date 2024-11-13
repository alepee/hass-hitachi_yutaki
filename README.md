[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

# Hitachi Yutaki Integration for Home Assistant

This custom integration allows you to control and monitor your Hitachi Yutaki heat pump through Home Assistant using a Modbus ATW-MBS-02 gateway.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alepee&repository=hass-hitachi_yutaki)

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
| ip_address | attribute | Gateway IP Address | - |
| availability | binary_sensor | Gateway Connection Status | - |

### Heat Pump Control Unit Device

#### Controls
| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | Unit Run/Stop | on/off |
| operation_mode | select | Unit Operation Mode | cool/heat/auto |

#### Temperatures
| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| outdoor_temp | sensor | Outdoor Ambient Temperature | °C |
| water_inlet_temp | sensor | Water Inlet Temperature | °C |
| water_outlet_temp | sensor | Water Outlet Temperature | °C |
| gas_temp | sensor | Gas Temperature | °C |
| liquid_temp | sensor | Liquid Temperature | °C |
| discharge_gas_temp | sensor | Discharge Gas Temperature | °C |
| evaporation_temp | sensor | Evaporation Temperature | °C |

#### System Status
| Entity | Type | Description | Values |
|--------|------|-------------|---------|
| defrost_active | binary_sensor | Defrost Status | on/off |
| solar_active | binary_sensor | Solar System Status | on/off |
| pump1_active | binary_sensor | Water Pump 1 Status | on/off |
| pump2_active | binary_sensor | Water Pump 2 Status | on/off |
| pump3_active | binary_sensor | Water Pump 3 Status | on/off |
| compressor_active | binary_sensor | Compressor Status | on/off |
| boiler_active | binary_sensor | Boiler Status | on/off |
| dhw_heater_active | binary_sensor | DHW Heater Status | on/off |
| space_heater_active | binary_sensor | Space Heater Status | on/off |
| smart_function_enabled | binary_sensor | Smart Function Status | on/off |

#### Performance Metrics
| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| water_flow | sensor | Water Flow Level | m³/h |
| pump_speed | sensor | Water Pump Speed | % |
| indoor_valve_opening | sensor | Indoor Expansion Valve Opening | % |
| outdoor_valve_opening | sensor | Outdoor Expansion Valve Opening | % |
| inverter_frequency | sensor | Inverter Operation Frequency | Hz |
| compressor_current | sensor | Compressor Running Current | A |
| power_consumption | sensor | Unit Power Consumption | kWh |

#### R134a Circuit (S80 Model Only)
| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| r134a_discharge_temp | sensor | R134a Discharge Temperature | °C |
| r134a_suction_temp | sensor | R134a Suction Temperature | °C |
| r134a_discharge_pressure | sensor | R134a Discharge Pressure | MPa |
| r134a_suction_pressure | sensor | R134a Suction Pressure | MPa |
| r134a_frequency | sensor | R134a Compressor Frequency | Hz |
| r134a_valve_opening | sensor | R134a Indoor Expansion Valve Opening | % |
| r134a_current | sensor | R134a Compressor Current | A |

### Heating/Cooling Circuit Device (up to 2 circuits)

Each circuit (if configured) provides:

| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | Circuit Run/Stop | on/off |
| heat_mode | select | Heat OTC Mode | disabled/points/gradient/fix |
| cool_mode | select | Cool OTC Mode | disabled/points/fix |
| heat_temp | number | Water Heating Temperature | °C (0-80) |
| cool_temp | number | Water Cooling Temperature | °C (0-80) |
| mode | select | Circuit Mode | eco/comfort |
| heat_eco_offset | number | Heat ECO Offset | °C (1-10) |
| cool_eco_offset | number | Cool ECO Offset | °C (1-10) |

#### Thermostat (if configured)
| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| thermostat_available | switch | Thermostat Availability | on/off |
| thermostat_temp | number | Thermostat Setting | °C (5.0-35.0) |
| room_temp | sensor | Room Temperature | °C |

### Domestic Hot Water Device (if configured)

| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | DHW Run/Stop | on/off |
| temperature | number | DHW Temperature Setting | °C (0-80) |
| boost | switch | DHW Boost | on/off |
| mode | select | DHW Demand Mode | standard/high_demand |
| current_temp | sensor | Current DHW Temperature | °C |

#### Anti-legionella
| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | Anti-legionella Run/Stop | on/off |
| temperature | number | Anti-legionella Temperature | °C (0-80) |

### Swimming Pool Device (if configured)

| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | Pool Run/Stop | on/off |
| temperature | number | Pool Temperature Setting | °C (0-80) |
| current_temp | sensor | Current Pool Temperature | °C |

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
