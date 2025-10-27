# Hitachi Yutaki – Complete Architectural Overhaul (v2.0.0-beta.3)

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/v2.0.0-beta.3/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/v2.0.0-beta.3)

A major architectural release implementing hexagonal architecture and domain-driven design, with robust Modbus connection recovery and comprehensive business API abstraction.

## ✨ What's New?

*   **Robust Modbus Connection Recovery:** Automatic reconnection with exponential backoff (1s, 2s, 4s intervals) and transparent recovery without Home Assistant restart. Fixes issue [#118](https://github.com/alepee/hass-hitachi_yutaki/issues/118) where the integration failed to recover from temporary network interruptions.
*   **Complete Hexagonal Architecture:** Pure business logic in domain layer (100% testable without Home Assistant mocks), adapters bridging domain with HA, and domain-driven entity organization.
*   **Domain-Driven Entity Structure:** Entities organized by business domains (circuit, compressor, control_unit, dhw, gateway, hydraulic, performance, pool, power, thermal) instead of technical grouping.
*   **Comprehensive Business API:** HitachiApiClient with typed methods for all controllable parameters, eliminating direct Modbus access from entities and providing natural data types (float for temperatures, bool for settings).
*   **Builder Pattern Implementation:** Type-safe entity creation with conditional logic based on device capabilities, replacing direct entity instantiation.
*   **Platform Orchestrators:** Simplified platform files acting as pure orchestrators, importing and calling domain builders.
*   **Enhanced Modularity:** Each domain is self-contained with its own sensors, switches, numbers, etc., improving maintainability and scalability.

## 🔧 Technical Improvements

*   **Data Conversion Enhancements:** Centralized deserialization logic with pattern-based naming (convert_from_tenths, convert_signed_16bit, convert_pressure) and fixed sensor readings for secondary compressor current and pressure sensors.
*   **Modbus Register Organization:** Logical device grouping (gateway, control_unit, primary_compressor, secondary_compressor, circuit_1, circuit_2, dhw, pool) for improved clarity and maintainability.
*   **Entity Identifier Updates:** Renamed r134a_ to secondary_compressor_ for better readability, enhanced alarm sensor to display descriptions as state with numeric codes as attributes.
*   **Code Quality:** Reduced sensor.py from 1657 to ~150 lines, eliminated code duplication, simplified import structure with clear domain boundaries.

## 📚 Documentation & Architecture

*   **Specialized Documentation:** New README files for each architectural layer:
    - [Domain Layer](custom_components/hitachi_yutaki/domain/README.md): Pure business logic
    - [Adapters Layer](custom_components/hitachi_yutaki/adapters/README.md): Infrastructure implementations
    - [Entities Layer](custom_components/hitachi_yutaki/entities/README.md): Domain-driven organization
*   **Updated Main README:** Reflects new architecture and project structure
*   **Comprehensive CHANGELOG:** Detailed migration notes and technical improvements

## 📝 Important Notes

*   **Breaking Changes:** This is a major architectural refactoring. While user-facing functionality remains the same, developers should review the new architecture documentation before contributing.
*   **Backward Compatibility:** Existing configurations continue to work without changes.
*   **Migration Guide:** See specialized README files in domain/, adapters/, and entities/ directories for detailed architectural information.
*   **Future-Ready:** Architecture prepared for HTTP-based gateways and persistent storage solutions.

## 🧪 Testing Needed

We would appreciate feedback on:
*   **Connection Recovery:** Test behavior during network interruptions and verify automatic reconnection works correctly.
*   **Entity Functionality:** Confirm all existing entities work as expected with the new architecture.
*   **Performance:** Verify that the new architecture doesn't impact response times or resource usage.
*   **Configuration:** Test that existing configurations load correctly and all settings are preserved.

## 🐛 Bug Reports

If you encounter any issues, please open a GitHub issue and include:
*   Your Home Assistant version.
*   Your configuration (heat pump model, gateway type).
*   Debug-level logs (especially for connection recovery and entity creation).
*   A clear description of the problem and reproduction steps.

## 🚀 Future Benefits

*   **Enhanced Testability:** Domain layer is 100% testable without Home Assistant mocks.
*   **Improved Maintainability:** Business logic centralized in domain layer, single point of truth for calculations.
*   **Better Extensibility:** Easy to add new entity types, gateways, or storage implementations.
*   **Cleaner Architecture:** Clear separation between business logic and infrastructure concerns.

Thanks for helping test this major architectural improvement that positions the Hitachi Yutaki integration for future growth and maintainability!
