# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
