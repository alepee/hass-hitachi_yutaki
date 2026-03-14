[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Translation status](https://hosted.weblate.org/widget/hass-hitachi_yutaki/source/svg-badge.svg)](https://hosted.weblate.org/engage/hass-hitachi_yutaki/)

# Hitachi air-to-water heat pumps Integration for Home Assistant

This custom integration allows you to control and monitor your Hitachi **Yutaki** and **Yutampo** air-to-water heat pumps through Home Assistant using an ATW-MBS-02 or HC-A(16/64)MB Modbus gateway.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alepee&category=integration&repository=hass-hitachi_yutaki)

## Compatibility

- **Compatible Models**: 2016 and newer Hitachi air-to-water heat pumps
- **Tested With**: Yutaki S80, Yutaki S, Yutaki S Combi, Yutampo R32
- **Required Hardware**: ATW-MBS-02 or HC-A(16/64)MB Modbus gateway

> **Important**: Models manufactured before 2016 use different Modbus registers and are not compatible. If you do have an older Heat Pump already equiped with a Modbus gateway, you can [open an issue](https://github.com/alepee/hass-hitachi_yutaki/issues/new?title=Pre-2016%20Heat%20Pump%20support%20request) if your have time to help me add support for your model.

## Features

The integration automatically detects your heat pump model and creates devices based on your system configuration:

- **Gateway** — connectivity and synchronization monitoring
- **Control Unit** — power, operating mode, temperatures (outdoor, water inlet/outlet), system status (defrost, alarms, compressor, boiler, pumps), hydraulic sensors, electrical and thermal energy tracking
- **Primary Compressor** — frequency, current, temperatures (gas, liquid, discharge, evaporator), expansion valve openings, cycle timing
- **Secondary Compressor** (S80 only) — frequency, current, temperatures, pressures, cycle timing
- **Circuit 1 & 2** — climate control with heating/cooling modes, ECO mode, OTC configuration, thermostat function
- **Domestic Hot Water** — water heater control, boost mode, anti-legionella treatment
- **Swimming Pool** (if configured) — power and temperature control
- **COP Sensors** — real-time Coefficient of Performance for heating, cooling, DHW, and pool with quality indicators

See the [full entity reference](docs/reference/entities.md) for a detailed list of every entity per device.

Additional highlights:
- Multi-language support ([help translate](https://hosted.weblate.org/engage/hass-hitachi_yutaki/))
- Resilient to gateway connection issues at startup
- Automated repair suggestions for gateway desynchronization
- Comprehensive alarm descriptions with translations
- Configurable: single/three phase power, external sensors, scan intervals

### Circuit Climate Modes

Circuit behavior depends on the system configuration:
- **Single circuit**: Exposes `off` / `heat` / `cool` / `auto` modes with direct global mode control
- **Two circuits**: Exposes `off` / `heat_cool` (power toggle only) — global mode is controlled via the Control Unit's `operation_mode` select to avoid conflicts between circuits

### COP Monitoring

Each COP sensor includes a `quality` attribute (`no_data`, `insufficient_data`, `preliminary`, `optimal`) to indicate measurement reliability. For best accuracy, configure external water temperature sensors — internal sensors have 1°C resolution.

The integration supports two calculation methods:
- **External sensors** (recommended): uses precise external temperature measurements with energy accumulation
- **Internal sensors** (default): uses built-in sensors, mitigating precision limitations through time-based accumulation

### Thermal Energy Tracking

Separate tracking for heating and cooling:
- **Real-time power** (`thermal_power_heating`, `thermal_power_cooling`) in kW
- **Daily energy** (auto-resets at midnight) in kWh
- **Total energy** (persistent across restarts) in kWh

Measurements are filtered: defrost cycles are excluded, and a post-cycle lock prevents counting thermal inertia noise after compressor stops.

<details>
<summary>Migration from v1.x</summary>

In v2.0.0, the following sensors have been **replaced** (old entities are automatically migrated):
- `thermal_power` → `thermal_power_heating`
- `daily_thermal_energy` → `thermal_energy_heating_daily`
- `total_thermal_energy` → `thermal_energy_heating_total`

The old sensors counted defrost cycles as energy production, resulting in unrealistic COP values (e.g., COP > 8). The new sensors correctly separate heating from cooling and filter defrost periods.
</details>

## Service Actions

### `hitachi_yutaki.set_room_temperature`

Sets the room thermostat temperature setpoint for a circuit climate entity. This is useful when the circuit is configured in thermostat mode with a room temperature sensor.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `entity_id` | Yes | Target climate entity (`climate.circuit_1`, `climate.circuit_2`) |
| `temperature` | Yes | Temperature setpoint in °C (0–50, step 0.1) |

**Example automation:**

```yaml
action:
  - action: hitachi_yutaki.set_room_temperature
    target:
      entity_id: climate.circuit_1
    data:
      temperature: 21.5
```

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

1. **Gateway selection**: Choose your gateway type (ATW-MBS-02 or HC-A(16/64)MB)
2. **Gateway configuration**: Connection details (name, IP, port, slave ID, scan interval). HC-A(16/64)MB also asks for the unit ID.
3. **Profile selection**: The integration auto-detects your heat pump model. You can override the detection if needed.
4. **Power & sensors**: Power supply type (single/three phase) and optional external entities for voltage, power, energy, and water temperatures (inlet/outlet) for more accurate COP and thermal calculations.

You can reconfigure the integration at any time via **Settings** > **Devices & Services** > **Hitachi Heat Pump** > **Configure**.

## Telemetry

This integration can optionally collect anonymous performance data to improve support for all heat pump models. **Telemetry is disabled by default** and requires explicit opt-in.

- **Off** — No data collected (default)
- **Basic** — Installation info + daily aggregated stats (once per day)
- **Full** — Fine-grained metrics every 5 minutes + one-time register snapshot

All data is identified by a non-reversible hash. No personal information, IP addresses, or location data is ever collected. You can change your level or disable telemetry at any time in the integration options.

See [Telemetry Reference](docs/reference/telemetry.md) for details on what is collected, and [Discussion #200](https://github.com/alepee/hass-hitachi_yutaki/discussions/200) for community context.

## Known Limitations

- **Modbus TCP only**: Direct serial Modbus is not supported.
- **Pre-2016 models**: Older Hitachi heat pumps use different register maps and are not compatible.
- **Temperature precision**: Internal temperature sensors have 1°C precision. Configure external sensors for more accurate COP.
- **Single gateway**: Each integration instance connects to one gateway. Multiple gateways require multiple instances.
- **Global operating mode**: Heat/cool/auto is shared across all circuits. With two circuits active, change mode via the Control Unit's `operation_mode` select.
- **No automatic discovery**: The gateway must be configured manually.

## Troubleshooting

### Gateway cannot connect

- Verify the gateway is powered on and connected to your network
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

- Check the `quality` attribute — `preliminary` or `optimal` quality is needed for reliable values
- Configure external water temperature sensors for better precision
- COP is filtered during defrost cycles and post-compressor shutdown
- COP sensors track heating and DHW separately — ensure you're reading the right sensor

### Heat pump control mode

The heat pump's external control mode must NOT be set to 'Local' (0). Set it to Air (1), Water (2), or Total (3) via: **System Configuration** > **General Options** > **External Control Option** > **Control Mode**.

## Development

This integration follows **Hexagonal Architecture** (Ports and Adapters). See the [developer documentation](docs/) for details:

- [Architecture](docs/architecture.md) — layers, data flow, domain-to-entity matrix
- [Getting Started](docs/development/getting-started.md) — setup, dev container, make targets
- [Adding Entities](docs/development/adding-entities.md) — step-by-step entity creation guide
- [API Layer & Data Keys](docs/development/api-data-keys.md) — API abstraction and data keys
- [Profiles](docs/development/profiles.md) — heat pump model detection and capabilities

## Translations

This integration is translated using [Weblate](https://hosted.weblate.org/engage/hass-hitachi_yutaki/).

[![Translation status](https://hosted.weblate.org/widget/hass-hitachi_yutaki/source/multi-auto.svg)](https://hosted.weblate.org/engage/hass-hitachi_yutaki/)

To help translate the integration into your language, visit the [Weblate project page](https://hosted.weblate.org/engage/hass-hitachi_yutaki/) and start contributing — no coding required!

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow.

## License

This project is under the MIT License. See the LICENSE file for details.

## Credits

This integration was developed by Antoine Lépée and is not affiliated with Hitachi Ltd.

## Support

For bugs and feature requests, please use the [GitHub issues](https://github.com/alepee/hass-hitachi_yutaki/issues) page.
