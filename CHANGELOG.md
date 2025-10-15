# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Implemented a new hexagonal architecture (Ports and Adapters) to decouple core logic from communication protocols. This introduces a clear **dependency injection** pattern, making the integration modular and easier to extend with new gateways (e.g., HTTP-based) in the future.
- Introduced a smart profile auto-detection mechanism. Each heat pump profile now contains its own **decentralized detection logic**, allowing for more complex and robust model identification without altering the core configuration flow.
- Added abstract storage interface to prepare for future persistent storage solutions, making data persistence implementation-agnostic.

### Changed
- **Major architectural refactoring** to align with hexagonal architecture principles:
  - Implemented complete abstraction layer between domain entities and Modbus gateway through a comprehensive business-level API
  - Removed all direct access to `coordinator.data` and `coordinator.async_write_register()` from entities
  - All entities now interact exclusively through the `HitachiApiClient` interface with typed methods (e.g., `get_circuit_current_temperature()`, `set_dhw_target_temperature()`)
  - Added dedicated getter/setter methods for all controllable parameters: unit control (power, mode), circuit control (power, temperatures, eco mode, thermostat, OTC), DHW control (power, temperatures, boost, anti-legionella), and pool control (power, temperatures)
  - Temperature methods work directly with `float` values in °C, boolean settings use natural `bool` types, and inverted logic is encapsulated internally (e.g., eco_mode register 0/1 → API exposes `True`/`False`)
  - Refactored all entity files (`climate.py`, `water_heater.py`, `switch.py`, `number.py`, `select.py`, `button.py`) to use the new API methods
- **Data conversion improvements**:
  - Centralized all data deserialization logic into register definitions with dedicated deserializer functions
  - Refactored conversion functions to use pattern-based naming: consolidated duplicate functions into `convert_from_tenths()` (generic /10 pattern), renamed `convert_temperature()` to `convert_signed_16bit()` (2's complement pattern), kept `convert_pressure()` for domain-specific MPa→bar conversion
  - Added comprehensive documentation explaining the four conversion patterns (from tenths, signed 16-bit, pressure, and direct values)
- Refactored complex business logic (COP, thermal power, compressor timing, electrical power) into a dedicated service layer using Dependency Injection.
- Fully decoupled domain entities from gateway implementation details by exposing system status (defrost, compressor running, pumps, heaters) through abstract properties.
- Reorganized Modbus register maps by logical device (e.g., `gateway`, `control_unit`, `primary_compressor`, `secondary_compressor`, `circuit_1`, `circuit_2`, `dhw`, `pool`) for improved clarity and maintainability.
- Moved all Modbus-specific constants (register addresses, bit masks for configuration and status) from shared `const.py` into the Modbus gateway layer (`api/modbus/registers/atw_mbs_02.py`).
- Renamed all `r134a_` entity identifiers to `secondary_compressor_` for better readability and consistency.
- Improved the alarm sensor to display the alarm description as its state (e.g., "Alarm 07"), moving the numeric code to an attribute for better user experience.
- Enhanced system state reporting with proper deserialization (synchronized, desynchronized, initializing) and operation state mapping.

### Removed
- Removed the redundant `target_temp` and `current_temp` number entities for climate circuits, as this functionality is now handled by the climate entity.

### Fixed
- Resolved circular import issues and entity creation bugs during architectural refactoring.
- Corrected temperature deserialization by properly differentiating between values stored in tenths (`*3` in ATW-MBS-02 doc) and signed 16-bit integers (`*1`). All setpoints and configuration temperatures now correctly converted from tenths.
- Fixed sensor readings: secondary compressor current (was off by factor of 10, now correctly in tenths of amperes) and pressure sensors (now correctly converting hundredths of MPa to bar: 510 raw = 5.10 MPa = 51.0 bar).
- Fixed unit power switch displaying "Unknown" due to inconsistent condition check between getter and setter methods.

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
