# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`set_room_temperature` service** — New entity platform service (`hitachi_yutaki.set_room_temperature`) to write the measured room temperature to the heat pump. Targets climate entities and enables automations to push ambient temperature readings when the Modbus thermostat is enabled.
- **Operation state numeric attribute** (issue [#187](https://github.com/alepee/hass-hitachi_yutaki/issues/187)) - The operation state entity now exposes the raw Modbus numeric value (0-11) as a `code` attribute, enabling simpler automation logic
- **Conditional circuit climate modes** (issue [#186](https://github.com/alepee/hass-hitachi_yutaki/issues/186)) - When two circuits are active, climate entities expose only `off`/`heat_cool` modes (power toggle only), since the operating mode is global. Single-circuit setups retain full `heat`/`cool`/`auto`/`off` mode control

### Fixed
- **COP DHW identical to COP Heating** (issue [#191](https://github.com/alepee/hass-hitachi_yutaki/issues/191)) - COP sensors now use `operation_state` (Modbus register 1090) instead of `hvac_action` to differentiate heating, DHW, cooling, and pool cycles. Fixes identical COP values for DHW and Heating since the v2.0.0 refactoring.
- **Anti-legionella binary sensor** (issue [#178](https://github.com/alepee/hass-hitachi_yutaki/issues/178)) - Read from STATUS registers instead of CONTROL registers for accurate anti-legionella cycle state
- **Config flow translations** - Added missing translations for gateway type and profile selection steps in config flow (both EN and FR)

### Added
- **Robust Modbus connection recovery mechanism**
- **Enhanced heat pump profile system** with explicit hardware capabilities per model:
  - New properties: `dhw_min_temp`, `dhw_max_temp`, `max_circuits`, `supports_cooling`, `max_water_outlet_temp`, `supports_high_temperature`
  - Each profile (S, S Combi, S80, M, Yutampo R32) now documents its exact hardware limits
  - Improved Yutampo R32 detection: correctly identified as S Combi (unit_model=1) with DHW-only configuration
  - Fixed S Combi detection to check all circuits (not just circuit 1) with exponential backoff retry logic and automatic reconnection on network interruptions. Fixes issue [#118](https://github.com/alepee/hass-hitachi_yutaki/issues/118) where the integration failed to recover from temporary network disconnections.
- **Complete hexagonal architecture implementation** with clear separation of concerns:
  - Domain layer with pure business logic and zero Home Assistant dependencies
  - Adapters layer bridging domain with Home Assistant
  - Enhanced testability with 100% testable domain layer
- **Domain-driven entity organization** replacing technical grouping with business domain structure (circuit, compressor, control_unit, dhw, gateway, hydraulic, performance, pool, power, thermal)
- **Builder pattern implementation** for all entity types with type-safe builders and conditional entity creation based on device capabilities
- **Comprehensive business-level API** (`HitachiApiClient`) with typed methods for all controllable parameters, eliminating direct Modbus access from entities
- **Smart profile auto-detection mechanism** with decentralized detection logic for more robust model identification
- **Recorder-based data rehydration** for COP and compressor timing sensors - historical data is automatically reconstructed from Home Assistant's Recorder on startup, eliminating data loss after restarts. The integration now leverages existing sensor history instead of maintaining separate persistent storage
- **Separate thermal energy sensors for heating and cooling** - New explicit sensors:
  - `thermal_power_heating` / `thermal_power_cooling`: Real-time power output
  - `thermal_energy_heating_daily` / `thermal_energy_cooling_daily`: Daily energy (resets at midnight)
  - `thermal_energy_heating_total` / `thermal_energy_cooling_total`: Total cumulative energy
  - Cooling sensors only created when unit has cooling circuits
- **Post-cycle thermal inertia tracking** - Thermal energy from system inertia is now correctly counted after compressor stops in both heating and cooling modes, until water temperature delta reaches zero
- **Automatic entity migration system** for seamless upgrade from v1.9.x to 2.0.0 - migrates entity unique_ids from old format (with slave_id) to new format, preserving entity history and IDs
- **Functional repair flow** for 1.9.3 → 2.0.0 migration - created dedicated `repairs.py` platform with proper RepairFlow implementation and automatic integration reload after repair completion
- **Hardware-based unique_id for config entries** (issue [#162](https://github.com/alepee/hass-hitachi_yutaki/issues/162)) - Config entries now use gateway's hardware identifier (read from Modbus Input Registers 0-2) as unique_id instead of IP+slave combination. This prevents duplicate entries for the same physical gateway and survives DHCP IP changes. Works in all environments including Docker containers. Includes automatic migration for existing installations and graceful fallback to IP-based unique_id if unavailable 

### Changed
- **Complete platform refactoring** to use domain-driven architecture - all platform files now act as pure orchestrators
- **Entity organization** moved from technical grouping (sensor/, switch/, etc.) to business domain grouping (entities/circuit/, entities/dhw/, etc.)
- **Data conversion improvements** with centralized deserialization logic and pattern-based naming
- **Modbus register organization** by logical device for improved clarity and maintainability
- **Alarm sensor enhancement** to display descriptions as state with numeric codes as attributes
- **System state reporting** with proper deserialization and operation state mapping
- **Storage strategy** - COP and compressor timing data now relies on Home Assistant's Recorder history instead of custom persistent storage, eliminating redundant data storage and ensuring consistency with Home Assistant's historical data
- **Thermal service refactoring** - Split monolithic `thermal.py` into modular package structure:
  - `calculators.py`: Pure thermal power calculation functions
  - `accumulator.py`: Energy accumulation logic with post-cycle lock mechanism
  - `service.py`: Orchestration layer coordinating calculations and accumulation
  - `constants.py`: Physical constants (water specific heat, flow conversion)
- **⚠️ BREAKING: Thermal energy calculation logic** - Fixes issue [#123](https://github.com/alepee/hass-hitachi_yutaki/issues/123):
  - Now correctly separates heating (ΔT > 0) from cooling (ΔT < 0)
  - **Defrost cycles are now filtered** (not counted as energy production)
  - **Post-cycle lock mechanism** prevents counting noise/fluctuations after compressor stops while still capturing thermal inertia energy in both heating and cooling modes
  - Only measures energy produced by the heat pump (with inertia tracking for both heating and cooling)
  - This results in accurate COP calculations (previously inflated by counting defrost as production)
  - Universal logic: works for heating circuits, DHW, and pool automatically based on water temperature delta

### Deprecated
- **⚠️ Old thermal energy sensors** (disabled by default, but still available for backward compatibility):
  - `thermal_power` → use `thermal_power_heating` instead
  - `daily_thermal_energy` → use `thermal_energy_heating_daily` instead
  - `total_thermal_energy` → use `thermal_energy_heating_total` instead
  - **Migration required**: Update your Energy Dashboard and automations to use new sensors
  - **Why deprecated**: Old sensors counted defrost cycles and lacked heating/cooling separation, resulting in incorrect COP values

### Removed
- **Legacy technical modules** and monolithic entity files in favor of domain-specific builders
- **Direct entity instantiation** replaced with builder pattern for better encapsulation
- **Legacy services directory** after successful migration to hexagonal architecture
- **Redundant climate number entities** (target_temp, current_temp) as functionality is now handled by climate entity

### Fixed
- **Profile detection robustness** - Fixed Yutampo R32 `detect()` returning `None` instead of `False` when `has_dhw` key is missing from data
- **Cooling capability detection** (issue [#177](https://github.com/alepee/hass-hitachi_yutaki/issues/177)) - Fixed system_config bitmask order that was incorrectly swapped during v2.0.0 refactoring, causing cooling hardware to not be detected on units with optional cooling (e.g., Yutaki S Combi). Regression from v1.9.x now resolved.
- **Architecture consistency** - all entity types now follow the same domain-driven pattern
- **Code duplication** eliminated across platforms
- **Import complexity** simplified with clear domain boundaries
- **Temperature deserialization** corrected by properly differentiating between tenths and signed 16-bit values
- **Sensor reading accuracy** for secondary compressor current and pressure sensors
- **Unit power switch** "Unknown" state issue due to inconsistent condition checks
- **Circular import issues** and entity creation bugs during architectural refactoring
- **COP measurement period calculation** - fixed negative time span values by ensuring measurements are sorted chronologically before calculating the measurement period
- **Legacy entities still present** after upgrade from v1.9.x - entities now migrate automatically with preserved history


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
