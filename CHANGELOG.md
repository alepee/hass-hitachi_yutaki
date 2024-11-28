# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2023-12-05

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
