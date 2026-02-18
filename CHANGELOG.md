# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `CONTRIBUTING.md` with contributor workflow documentation

### Fixed
- Fix HC-A(16/64)MB outdoor compressor registers mapped to wrong address block (5000+offset instead of 30000+offset), causing discharge temp, evaporator temp, current, frequency, and EVO opening to show as unavailable ([#96](https://github.com/alepee/hass-hitachi_yutaki/issues/96))
- Use HP-level outlet register (1201) for correct DHW/pool COP calculation — register 1094 measures circuit outlet which becomes stale when the 3-way valve redirects to the tank, causing zero thermal power and no COP during DHW runs ([#205](https://github.com/alepee/hass-hitachi_yutaki/issues/205))
- Update Dutch (nl) translations

### Changed
- GitHub branch protection: rulesets for `main` (merge-only, required CI) and `dev` (squash-only, required CI, admin bypass)
- `CLAUDE.md`: updated branch strategy, git conventions, and translations sections

## [2.0.0] - 2026-02-12

A major rewrite of the integration with hexagonal architecture, multi-gateway support, and significantly improved accuracy for thermal and COP calculations.

### Highlights

- **Multi-gateway support**: HC-A(16/64)MB alongside ATW-MBS-02
- **Hexagonal architecture**: pure domain layer, testable without Home Assistant
- **Accurate thermal energy**: separate heating/cooling tracking, defrost filtering
- **Seamless migration**: automatic entity migration from v1.9.x with preserved history

### Added
- **HC-A(16/64)MB gateway support** — New Modbus gateway type alongside ATW-MBS-02. Both HC-A16MB and HC-A64MB are protocol-identical (same registers, same features — only the capacity differs: 16 vs 64 indoor units). Introduces a register abstraction layer (`HitachiRegisterMap` ABC) enabling polymorphic gateway support with separate read/write address ranges, unit_id-based address computation, and gateway-specific deserialization
- **Outdoor unit registers for HC-A(16/64)MB gateway** ([#96](https://github.com/alepee/hass-hitachi_yutaki/issues/96)) — Compressor frequency, current, discharge/liquid/gas/evaporator temperatures, and expansion valve openings now available on HC-A-MB gateways
- **New heat pump profiles** — YCC and Yutaki SC Lite profiles for models only available via HC-A(16/64)MB gateway
- **External energy sensor (`energy_entity`)** — New optional configuration to replace the Modbus power consumption register with an external lifetime energy sensor (`device_class=energy`, kWh, `TOTAL_INCREASING`). The `power_consumption` entity exposes a `source` attribute for transparency
- **`set_room_temperature` service** — New entity platform service to write measured room temperature to the heat pump via climate entities, enabling automations when the Modbus thermostat is enabled
- **Operation state numeric attribute** ([#187](https://github.com/alepee/hass-hitachi_yutaki/issues/187)) — Raw Modbus numeric value (0-11) exposed as a `code` attribute for simpler automation logic
- **Conditional circuit climate modes** ([#186](https://github.com/alepee/hass-hitachi_yutaki/issues/186)) — Two-circuit setups expose only `off`/`heat_cool` (power toggle); single-circuit retains full `heat`/`cool`/`auto`/`off` control
- **Complete hexagonal architecture** — Domain layer with pure business logic (zero HA dependencies), adapters layer bridging domain with Home Assistant, 100% testable domain layer
- **Domain-driven entity organization** — Business domain structure (circuit, compressor, control_unit, dhw, gateway, hydraulic, performance, pool, power, thermal) with builder pattern for all entity types
- **Robust Modbus connection recovery** — Exponential backoff retry logic with automatic reconnection on network interruptions ([#118](https://github.com/alepee/hass-hitachi_yutaki/issues/118))
- **Enhanced heat pump profile system** — Explicit hardware capabilities per model (`dhw_min_temp`, `dhw_max_temp`, `max_circuits`, `supports_cooling`, `max_water_outlet_temp`, `supports_high_temperature`)
- **Smart profile auto-detection** — Decentralized detection logic with improved Yutampo R32 and S Combi detection
- **Recorder-based data rehydration** — COP and compressor timing sensors automatically reconstruct history from HA Recorder on startup, eliminating data loss after restarts
- **Separate thermal energy sensors for heating and cooling**:
  - `thermal_power_heating` / `thermal_power_cooling`: Real-time power output
  - `thermal_energy_heating_daily` / `thermal_energy_cooling_daily`: Daily energy (resets at midnight)
  - `thermal_energy_heating_total` / `thermal_energy_cooling_total`: Total cumulative energy
- **Post-cycle thermal inertia tracking** — Thermal energy from system inertia correctly counted after compressor stops
- **Automatic entity migration** — Seamless upgrade from v1.9.x to 2.0.0 with preserved entity history and IDs
- **Functional repair flow** — Dedicated `repairs.py` for 1.9.x → 2.0.0 migration with automatic integration reload
- **Hardware-based unique_id** ([#162](https://github.com/alepee/hass-hitachi_yutaki/issues/162)) — Config entries use gateway hardware identifier (Modbus Input Registers 0-2) instead of IP+slave, preventing duplicates and surviving DHCP changes
- **Annotated Modbus register scanner** — New `scripts/scan_gateway.py` tool with `make scan` target for diagnosing register values across all gateway types, with human-readable annotations and scan reference documentation

### Changed
- **Minimum Home Assistant version** raised to 2025.1.0 to align with `WaterHeaterEntityDescription` component signature
- **Minimum Python version** raised to 3.13
- **CI tests against min and latest HA versions** via matrix (HA 2025.1.0 and latest)
- **Complete platform refactoring** to domain-driven architecture — all platform files act as pure orchestrators
- **Entity organization** moved from technical grouping to business domain grouping
- **Modbus register organization** by logical device for improved clarity
- **Alarm sensor** displays descriptions as state with numeric codes as attributes
- **Storage strategy** — COP and compressor data relies on HA Recorder instead of custom storage
- **Thermal service** split into modular package: `calculators.py`, `accumulator.py`, `service.py`, `constants.py`
- **Thermal energy classification uses operation mode** ([#196](https://github.com/alepee/hass-hitachi_yutaki/discussions/196)) — DHW and pool cycles now force heating classification regardless of ΔT sign, preventing transient negative deltas from being incorrectly counted as cooling energy
- **Sensor subclasses extracted into dedicated package** — `entities/base/sensor.py` split into `entities/base/sensor/` package with specialized subclasses (COP, thermal, timing) for better maintainability
- **Register map factory** extracted into `api/__init__.py`, eliminating duplication
- **⚠️ BREAKING: Thermal energy calculation logic** ([#123](https://github.com/alepee/hass-hitachi_yutaki/issues/123)):
  - Correctly separates heating (ΔT > 0) from cooling (ΔT < 0)
  - Defrost cycles are now filtered (not counted as energy production)
  - Post-cycle lock mechanism prevents counting noise after compressor stops
  - Results in accurate COP calculations (previously inflated by defrost)

### Deprecated
- **⚠️ Old thermal energy sensors** (disabled by default, still available for backward compatibility):
  - `thermal_power` → use `thermal_power_heating` instead
  - `daily_thermal_energy` → use `thermal_energy_heating_daily` instead
  - `total_thermal_energy` → use `thermal_energy_heating_total` instead
  - **Migration required**: Update your Energy Dashboard and automations to use the new sensors

### Removed
- Legacy technical modules and monolithic entity files in favor of domain-specific builders
- Direct entity instantiation replaced with builder pattern
- Legacy services directory
- Redundant climate number entities (target_temp, current_temp) — now handled by climate entity

### Fixed
- **Anti-legionella temperature range** ([#178](https://github.com/alepee/hass-hitachi_yutaki/issues/178)) — DHW anti-legionella target temperature now uses profile-based min/max instead of hardcoded values, respecting each model's actual capabilities
- **COP DHW identical to COP Heating** ([#191](https://github.com/alepee/hass-hitachi_yutaki/issues/191)) — COP sensors now use `operation_state` to differentiate heating, DHW, cooling, and pool cycles
- **Anti-legionella binary sensor** ([#178](https://github.com/alepee/hass-hitachi_yutaki/issues/178)) — Read from STATUS registers instead of CONTROL registers
- **Cooling capability detection** ([#177](https://github.com/alepee/hass-hitachi_yutaki/issues/177)) — Fixed system_config bitmask order regression from v1.9.x
- **OTC cooling serialization for HC-A(16/64)MB** — Correct mapping (Disabled=0, Points=1, Fix=2)
- **Recorder database access warning** — Use recorder executor for database operations
- **Pressure sensor error handling** — `0xFFFF` sentinel check in both gateway register maps
- **Config flow translations** — Added missing translations for gateway/profile selection (EN and FR)
- **Profile detection robustness** — Yutampo R32 `detect()` no longer returns `None` when `has_dhw` is missing
- **Temperature deserialization** — Properly differentiates between tenths and signed 16-bit values
- **Sensor reading accuracy** for secondary compressor current and pressure sensors
- **Unit power switch** "Unknown" state due to inconsistent condition checks
- **COP measurement period** — Fixed negative time span values
- **Legacy entities** — Automatic migration with preserved history

## [1.9.3] - 2025-10-06

### Fixed
- Fixed aberrant COP (Coefficient of Performance) values by implementing comprehensive data validation and intelligent unit detection for power sensors
- Added robust validation for all input parameters: temperature ranges (-10°C to 80°C), water flow rates (0.1 to 10.0 m³/h), temperature differences (0.5 to 30 K), power ranges (0.1 to 50.0 kW thermal, 0.1 to 20.0 kW electrical), and final COP values (0.5 to 8.0)
- Implemented automatic power unit detection (W vs kW) using `unit_of_measurement` attribute with intelligent fallback detection based on value ranges
- Added validation for energy accumulation to prevent calculation errors in COP measurements
- Enhanced debug logging for unit detection, validation failures, and COP calculations

### Changed
- Improved COP calculation accuracy by rejecting invalid data instead of producing incorrect values
- Enhanced support for external power and voltage sensors with automatic unit detection
- Updated power unit handling to seamlessly support both W and kW sensors
- Options flow: avoid providing `default=None` to entity selectors to prevent the UI error "Entity None is neither a valid entity ID nor a valid UUID" when opening Options. ([#109](https://github.com/alepee/hass-hitachi_yutaki/issues/109))
- Options flow: stop storing the `config_entry` on the options flow instance to comply with Home Assistant deprecation and silence the warning that will become an error in 2025.12. ([#109](https://github.com/alepee/hass-hitachi_yutaki/issues/109))
 - CI: update GitHub Actions `actions/setup-python` to v6
 - Dev tooling: bump `ruff` to 0.13.3

## [1.9.2] - 2025-09-05

### Fixed
- Fixed pymodbus compatibility issue with Home Assistant 2025.9.0+ by implementing automatic version detection for the device/slave parameter. The integration now works with both pymodbus < 3.10.0 (using `slave` parameter) and pymodbus >= 3.10.0 (using `device_id` parameter), ensuring compatibility across all Home Assistant versions. ([#97](https://github.com/alepee/hass-hitachi_yutaki/issues/97))

## [1.9.1] - 2025-07-22

### Changed
- Improved error handling in the data update coordinator to consistently create a repair issue in Home Assistant for any Modbus or network communication error.

### Fixed
- Resolved an issue where a loss of IP connectivity to the Modbus gateway could cause the integration to crash or behave unexpectedly. The integration now correctly handles network errors (`OSError`), ensuring that all entities become `unavailable` and properly recover once the connection is restored. ([#76](https://github.com/alepee/hass-hitachi_yutaki/issues/76))

## [1.9.0] - 2025-07-07

### Added
- New sensor to monitor the gateway's synchronization state (`Synchronized`, `Desynchronized`, `Initializing`).
- Pre-flight check during setup and updates to verify gateway synchronization status. This creates a persistent notification ("Repair") if the gateway is desynchronized, guiding the user to resolve the issue.

### Changed
- Improved startup resilience. The integration now caches the heat pump's configuration during the first successful setup. This ensures that all devices and entities are registered during subsequent Home Assistant startups, even if the heat pump is temporarily offline.

### Fixed
- Resolved a critical issue where all integration entities would disappear if the heat pump was offline when Home Assistant started. Entities will now appear as `unavailable` until the connection is restored.

## [1.8.2] - 2025-06-26

### Fixed
- Corrected the HACS installation link in `README.md` to ensure it redirects correctly.

### Changed
- Updated development dependencies, including `ruff` to v0.12.0.

## [1.8.1] - 2025-05-12

### Added
- New "Anti-legionella Cycle" button entity to manually start a high temperature anti-legionella treatment cycle.
- New binary sensor entity (`antilegionella_cycle`) indicating if an anti-legionella cycle is currently running.

### Changed
- Removed unused or redundant Domestic Hot Water (DHW) entities: DHW current temperature sensor, DHW target temperature number, DHW power switch, high demand switch, and periodic anti-legionella switch.
- Improved English and French translations for new entities and advanced configuration (water inlet/outlet temperature entities).

## [1.8.0] - 2025-05-11

### Changed
- The integration now allows configuration with central control modes Air (1), Water (2), or Total (3). Only Local (0) is forbidden.
- Error messages and documentation updated to reflect this change.
- The documentation now recommends using Air (1) mode for most installations.
- Support for Hitachi Yutampo R32 machines (requires 'Total' (3) mode).
- Bump ruff from 0.11.2 to 0.11.8 ([#50](https://github.com/alepee/hass-hitachi_yutaki/pull/50))
- Updated development dependencies and minor fixes.

## [1.7.1] - 2025-03-27

### Changed
- Replaced standard DHW preset with heat pump mode
- Migrated from Pylint to Ruff for code linting
- Updated development dependencies (Ruff to 0.11.2, pre-commit to 4.2.0)

### Added
- Added ffmpeg dependency to development environment

## [1.7.0] - 2025-03-19

### Added
- Implemented WaterHeaterEntity for Domestic Hot Water (DHW) control
- Better integration with Home Assistant UI for water heater controls
- Support for standard operation modes: off, standard, and high demand

## [1.6.1] - 2025-03-10

### Fixed
- Fixed issue with multiple heat pumps not generating unique entity IDs
- Added config entry ID to all entity unique IDs to ensure uniqueness across multiple instances

## [1.6.0] - 2025-02-06

### Added
- New thermal energy monitoring sensors:
  - Real-time thermal power output (kW)
  - Daily thermal energy production with midnight auto-reset (kWh)
  - Total cumulative thermal energy production (kWh)
- Detailed monitoring attributes:
  - Temperature differential and water flow tracking
  - Average power calculation over measurement periods
  - Precise measurement timing with compressor state tracking
- Full translations for all new features in French and English

## [1.5.2] - 2025-01-16

### Changed
- Optimized default sensor visibility based on configuration and relevance for standard users

## [1.5.1] - 2025-01-16

### Fixed
- Compatibility with latest pymodbus API

## [1.5.0] - 2025-01-16

### Added
- Improved logging for COP calculation and system state monitoring

### Changed
- Updated pymodbus dependency to match Home Assistant's version
- Optimized COP calculation parameters for better accuracy

## [1.5.0-b7] - 2025-01-12

### Added
- Added quality indicators for COP measurements (no_data, insufficient_data, preliminary, optimal)
- Added translations for COP quality indicators in French and English

### Fixed
- Fixed sample size and interval for more accurate COP calculation

## [1.5.0-b6] - 2025-01-06

### Fixed
- Fixed COP calculation by applying water flow conversion (raw value was used instead of m³/h)

## [1.5.0-b5] - 2025-01-03
### Fixed
- Fixed COP calculation by removing incorrect water flow division
- Added more detailed debug logging for thermal power calculation

## [1.5.0-b4] - 2025-01-02

### Added
- Added runtime and rest time sensors for both compressors
- Added detailed logging for power calculations
- Added debug information for thermal power calculation
- Added comprehensive logging for COP measurements and accumulation

### Changed
- Moved cycle time sensors to compressor devices for better organization
- Optimized COP calculation with more detailed debug information
- Simplified sensor code by moving value validation to conversion methods

### Fixed
- Fixed temperature conversion for special values (0xFFFF)
- Fixed water flow value scaling
- Fixed double conversion issue for temperature and pressure sensors
- Fixed connectivity sensor state calculation

### Added
- Added detailed logging for power calculations
- Added debug information for thermal power calculation
- Added comprehensive logging for COP measurements and accumulation

## [1.5.0-b3] - 2024-12-19

### Added
- Added external temperature entities configuration for more accurate COP calculations
- Added support for two COP calculation methods:
  - Moving median over 10 measurements when using external temperature sensors
  - Energy accumulation over 15 minutes when using internal sensors

### Changed
- Modified configuration flow to include temperature entity selection
- Improved COP calculation accuracy with external temperature sensors
- Refactored sensor code to reduce complexity and improve maintainability

### Documentation
- Updated configuration documentation with new temperature entity options
- Added explanation of COP calculation methods in the documentation

## [1.5.0-b2] - 2024-12-18

### Added
- Added power meter entity configuration option for more accurate COP calculations
- Added support for external power meter in sensor calculations

### Changed
- Modified configuration flow to include power meter entity selection
- Updated COP calculations to use power meter readings when available
- Enhanced power consumption accuracy with direct power meter readings

### Documentation
- Updated README with power meter configuration instructions
- Added power meter entity option in configuration documentation

## [1.5.0-b1] - 2024-12-14

### Added
- Added voltage entity configuration option for more accurate power calculations
- Introduced new configuration schemas for gateway, power supply and advanced settings
- Added support for custom voltage entity in sensor calculations

### Changed
- Modified configuration flow to include voltage entity selection
- Updated power consumption calculations to use voltage entity when available
- Enhanced system configuration flexibility with new voltage setup options

## [1.5.0-b0] - 2024-12-13

### Added
- New COP (Coefficient of Performance) sensor with real-time calculation
- Power supply type configuration (single-phase/three-phase)
- Enhanced power calculations for S80 models with dual compressor support

### Changed
- Improved power consumption calculations with smoothing algorithm
- Updated configuration options to include power supply type
- Enhanced accuracy of energy measurements

## [1.4.2] - 2024-12-11

### Changed
- Improved operation state sensor with more descriptive state values

## [1.4.1] - 2024-12-11

### Changed
- Downgraded pymodbus dependency to 3.6.9 to match Home Assistant's modbus integration

## [1.4.0] - 2024-12-11

### Added
- New diagnostic sensor "Operation State" showing detailed heat pump operation mode
- New diagnostic sensor "Compressor Cycle Time" measuring average time between compressor starts

### Changed
- Updated French and English translations for new sensors

## [1.3.4] - 2024-12-05

### Changed
- Removed unnecessary dependency to Home Assistant's modbus integration since we only use pymodbus library

## [1.3.3] - 2024-12-05

### Fixed
- Changed temperature conversion to use integers instead of floats as documented by Hitachi
- Fixed Pylint warnings by implementing missing abstract methods in ClimateEntity

## [1.3.2] - 2024-11-29

### Fixed
- Fixed unique_id generation in switch and number entities to prevent mismatched entities

## [1.3.1] - 2024-11-29

### Fixed
- Fixed register key double prefixing issue in switch and number entities causing some controls to fail

## [1.3.0] - 2024-11-29

### Removed
- Removed climate entity for DHW control in favor of more appropriate water heater entity type

## [1.2.0] - 2024-11-29

### Added
- Added new compressor diagnostic sensors:
  - Gas Temperature (TG)
  - Liquid Temperature (TI)
  - Discharge Temperature (TD)
  - Evaporator Temperature (TE)
  - Indoor Expansion Valve Opening (EVI)
  - Outdoor Expansion Valve Opening (EVO)

## [1.1.1] - 2024-11-29

### Fixed
- Fixed alarm code descriptions not loading

## [1.1.0] - 2024-11-28

### Added
- Added detailed error descriptions for all alarm codes
- Improved alarm code sensor to display both code and description

## [1.0.0] - 2024-11-05

### Added
- Initial release of the Hitachi Yutaki integration
- Basic configuration flow with connection validation
- Multi-language support (English and French)
- Automatic model detection and feature discovery
- Support for Yutaki S, S Combi, S80, and M models
- Climate control features:
  - Power control per circuit
  - Operation mode selection (Heat/Cool/Auto)
  - Target temperature adjustment
  - Comfort/Eco presets
  - Outdoor Temperature Compensation (OTC)
- DHW (Domestic Hot Water) control:
  - Power control
  - Target temperature adjustment
  - Boost mode
  - Anti-legionella function
  - High demand mode
- Pool heating control (if configured)
- Monitoring features:
  - Temperature sensors (outdoor, water inlet/outlet, circuits, DHW)
  - Component status (compressors, pumps, heaters)
  - Compressor frequencies and currents
  - Power consumption
  - Alarm codes
- Advanced configuration options:
  - Circuit-specific settings
  - Thermostat configuration
  - OTC calculation methods
  - ECO mode offsets
- Special features for S80 model:
  - Secondary compressor monitoring
  - R134a circuit sensors

### Changed
- N/A (Initial release)

### Deprecated
- N/A (Initial release)

### Removed
- N/A (Initial release)

### Fixed
- N/A (Initial release)

### Security
- Validation of Modbus connection parameters
- Proper error handling for Modbus communication
