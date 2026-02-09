# Hitachi Yutaki v2.0.0-rc.1 — Release Candidate

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/v2.0.0-rc.1/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/v2.0.0-rc.1)

First Release Candidate for v2.0.0 — a major rewrite of the integration with hexagonal architecture, multi-gateway support, and significantly improved accuracy for thermal and COP calculations.

## 🎯 Highlights

- **Multi-gateway support**: HC-A(16/64)MB alongside ATW-MBS-02
- **Hexagonal architecture**: pure domain layer, testable without Home Assistant
- **Accurate thermal energy**: separate heating/cooling tracking, defrost filtering
- **Seamless migration**: automatic entity migration from v1.9.x with preserved history

## ✨ New Features

### HC-A(16/64)MB Gateway Support

The integration now supports the **HC-A16MB** and **HC-A64MB** Modbus gateways alongside the existing ATW-MBS-02. Both gateways are protocol-identical (same registers, same features — only the capacity differs: 16 vs 64 indoor units).

Key differences handled transparently by the integration:

| Aspect | ATW-MBS-02 | HC-A(16/64)MB |
|---|---|---|
| Address scheme | Fixed registers | `5000 + unit_id × 200 + offset` |
| Pool target temp | Tenths (÷10) | Integer °C |
| Unit mode write | Cool/Heat/Auto | Cool/Heat only (no Auto) |
| Unit mode read | Single value | Bitmask (B0: heat, B1: auto) |
| Cooling OTC | 4 options | 3 options (no gradient) |
| Primary compressor | 8 registers | 3 registers |

Select **Modbus HC-A(16/64)MB (Beta)** during setup. A `Unit ID` field (0-15) allows targeting a specific indoor unit on multi-unit installations.

### New Heat Pump Profiles

Three new profiles available exclusively with HC-A(16/64)MB:
- **Yutaki SC Lite** (unit_model=4) — S Combi variant, single circuit
- **Yutampo R32** (unit_model=5) — DHW-only, now detected directly (no heuristic needed)
- **YCC** (unit_model=6) — Yutaki Commercial Controller

### External Energy Sensor

Replace the Modbus power consumption register with an external energy sensor (e.g., Shelly EM, smart meter). Configure in **Settings > Devices & Services > Hitachi Yutaki > Configure**. The `power_consumption` entity exposes a `source` attribute for transparency.

### `set_room_temperature` Service

Push measured room temperature to the heat pump when the Modbus thermostat is enabled:

```yaml
service: hitachi_yutaki.set_room_temperature
target:
  entity_id: climate.hitachi_circuit_1
data:
  temperature: "{{ states('sensor.salon_temperature') }}"
```

### Separate Thermal Energy Sensors

New explicit sensors for heating and cooling:
- `thermal_power_heating` / `thermal_power_cooling` — Real-time power output
- `thermal_energy_heating_daily` / `thermal_energy_cooling_daily` — Daily energy (resets at midnight)
- `thermal_energy_heating_total` / `thermal_energy_cooling_total` — Total cumulative energy

### Other New Features

- **Operation state numeric attribute** ([#187](https://github.com/alepee/hass-hitachi_yutaki/issues/187)) — Raw Modbus value (0-11) as `code` attribute
- **Conditional circuit climate modes** ([#186](https://github.com/alepee/hass-hitachi_yutaki/issues/186)) — Two circuits: `off`/`heat_cool` only; single circuit: full mode control
- **Robust Modbus connection recovery** — Exponential backoff with auto-reconnection ([#118](https://github.com/alepee/hass-hitachi_yutaki/issues/118))
- **Enhanced profile system** — Explicit hardware capabilities per model
- **Smart profile auto-detection** — Improved detection for all models
- **Recorder-based data rehydration** — COP and compressor history reconstructed on startup
- **Hardware-based unique_id** ([#162](https://github.com/alepee/hass-hitachi_yutaki/issues/162)) — Survives DHCP changes, prevents duplicate entries

## 🏗️ Architecture

v2.0.0 is a complete rewrite following **hexagonal architecture** (ports and adapters):

- **Domain layer** (`domain/`) — Pure business logic, zero HA dependencies, 100% testable
- **Adapters layer** (`adapters/`) — Bridges domain with Home Assistant
- **Entities layer** (`entities/`) — Organized by business domain (circuit, compressor, control_unit, dhw, gateway, hydraulic, performance, pool, power, thermal)
- **Builder pattern** for all entity types with conditional creation based on device capabilities
- **114 tests** covering domain services, profiles, register maps, and entity migration

## ⚠️ Breaking Changes

### Thermal Energy Calculation Logic

[#123](https://github.com/alepee/hass-hitachi_yutaki/issues/123) — The thermal energy calculation has been fundamentally improved:
- Correctly separates heating (ΔT > 0) from cooling (ΔT < 0)
- **Defrost cycles are now filtered** (no longer counted as energy production)
- Post-cycle lock mechanism prevents counting noise after compressor stops
- **COP values are now accurate** (previously inflated by defrost counting)

### Deprecated Thermal Sensors

Old sensors are disabled by default but still available:
- `thermal_power` → use `thermal_power_heating`
- `daily_thermal_energy` → use `thermal_energy_heating_daily`
- `total_thermal_energy` → use `thermal_energy_heating_total`

**⚡ Action required:** Update your Energy Dashboard and automations to use the new sensors.

### Removed Entities

- Redundant climate number entities (`target_temp`, `current_temp`) — now handled by the climate entity directly

## 🐛 Bug Fixes

- **COP DHW identical to COP Heating** ([#191](https://github.com/alepee/hass-hitachi_yutaki/issues/191)) — Uses `operation_state` to differentiate cycle types
- **Anti-legionella binary sensor** ([#178](https://github.com/alepee/hass-hitachi_yutaki/issues/178)) — Read from STATUS instead of CONTROL registers
- **Cooling capability detection** ([#177](https://github.com/alepee/hass-hitachi_yutaki/issues/177)) — Fixed bitmask order regression from v1.9.x
- **OTC cooling serialization** for HC-A(16/64)MB — Correct 3-option mapping
- **Recorder database access** — Use recorder executor for database operations
- **Pressure sensor** — `0xFFFF` sentinel check in both gateway register maps
- **Config flow translations** — Missing EN and FR translations for gateway/profile steps
- **Profile detection** — Yutampo R32 no longer returns `None` when `has_dhw` is missing
- **Temperature deserialization** — Properly differentiates tenths vs signed 16-bit
- **Secondary compressor** sensor accuracy for current and pressure
- **Unit power switch** "Unknown" state
- **COP measurement period** negative time span values
- **Legacy entities** — Automatic migration with preserved history

## 📦 Installation

### From v1.9.x (first install of v2.0.0)

1. Update via HACS to v2.0.0-rc.1
2. Restart Home Assistant
3. A repair notification will appear — click **Fix** to configure gateway type and heat pump profile
4. Entity migration runs automatically, preserving history

### From v2.0.0-beta.x

1. Update via HACS to v2.0.0-rc.1
2. Restart Home Assistant
3. No migration needed

## 🐛 Bug Reports

If you encounter issues, please report with:
- Home Assistant version
- Heat pump model and gateway type (ATW-MBS-02 or HC-A(16/64)MB)
- Relevant logs (`custom_components.hitachi_yutaki`)

---

**Full Changelog:** [v2.0.0-beta.12...v2.0.0-rc.1](https://github.com/alepee/hass-hitachi_yutaki/compare/v2.0.0-beta.12...v2.0.0-rc.1)
