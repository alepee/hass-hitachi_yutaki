# Release Notes - Beta.12

**Release Date**: 2026-02-07
**Version**: 2.0.0-beta.12
**Status**: ✅ Released

---

## Overview

Beta.12 fixes COP DHW values being identical to COP Heating (issue #191), adds a new `set_room_temperature` entity platform service that allows automations to push the measured room temperature to the heat pump when the Modbus thermostat is enabled, and introduces support for an external energy sensor (`CONF_ENERGY_ENTITY`) to replace the Modbus power consumption register.

---

## What's New

### External Energy Sensor (`CONF_ENERGY_ENTITY`)

The `power_consumption` sensor relies exclusively on Modbus register 1098 (kWh cumulative). Some models (e.g., Yutaki S80) don't have a reliable energy counter, and users may also have more accurate external energy meters (e.g., Shelly EM, smart meters).

**New configuration option**: `energy_entity` — an optional external lifetime energy sensor (`device_class=energy`, kWh, `TOTAL_INCREASING`) that replaces the Modbus register for the `power_consumption` entity.

**Behavior**:
- If configured, the external sensor is used **exclusively** (no fallback to Modbus — avoids value jumps on `TOTAL_INCREASING`)
- If not configured, Modbus register 1098 is used as today
- Available in both config flow (power step) and options flow (sensors step)
- The `power_consumption` entity exposes a `source` attribute: the external entity_id or `"gateway"`

### `set_room_temperature` Entity Platform Service

The ATW-MBS-02 gateway exposes R/W registers for "Thermostat Room Temperature" per circuit (register 1012 for circuit 1, register 1023 for circuit 2). When the Modbus thermostat is enabled (`switch.thermostat`), the heat pump expects the BMS to push the measured ambient temperature. These registers were previously read-only in the integration.

**New service**: `hitachi_yutaki.set_room_temperature`

```yaml
service: hitachi_yutaki.set_room_temperature
target:
  entity_id: climate.hitachi_circuit_1
data:
  temperature: "{{ states('sensor.salon_temperature') }}"
```

**Use case**: Automations that pick the room with the highest heating demand and write its temperature to the heat pump, replacing direct Modbus writes via the generic Modbus integration.

**Details**:
- Targets climate entities only (`climate.hitachi_circuit_1`, `climate.hitachi_circuit_2`)
- Temperature range: 0–50°C with 0.1°C precision
- Register value stored as tenths (e.g., 22.5°C → 225)
- Full service UI in Developer Tools > Services with number selector
- Translations: English and French

---

## Bug Fixes

### COP DHW Identical to COP Heating

**Issue**: [#191](https://github.com/alepee/hass-hitachi_yutaki/issues/191)

Since the v2.0.0 hexagonal refactoring, COP DHW and COP Heating showed identical values. Mode filtering relied on `hvac_action` (derived from `unit_mode` register 1001), which only distinguishes heating from cooling — DHW and pool cycles were never differentiated.

**Solution**: Replace `hvac_action` with `operation_state` (Modbus register 1090) which precisely identifies the active cycle type:

| `operation_state` | COP sensor |
|---|---|
| `operation_state_heat_thermo_on` | COP Heating |
| `operation_state_cool_thermo_on` | COP Cooling |
| `operation_state_dhw_on` | COP DHW |
| `operation_state_pool_on` | COP Pool |

- Filtering applied both in live updates (`COPService._is_mode_matching`) and Recorder rehydration (`async_replay_cop_history`)
- New `operation_state` field added to `COPInput` domain model
- Unit tests: 138 lines covering all mode combinations

**Commit**: `05a9f01`

---

## Breaking Changes

**None** - This release is fully backward compatible.

---

## Known Issues

Remaining from previous betas:
- **#176**: Auto-detection failure for some Yutaki S Combi models (fixable via Configure)
- **#178**: Potential remaining issue — footnote (*9) requires anti-legionella function enabled on LCD
- **#179**: Migration UX could be improved
- **#166**: COP values in graphs need refinement
- **#167**: Modbus transaction ID errors (intermittent)
- **#180**: Gateway sync status stuck on "Initialising"
- **#160**: Thermal inertia in power calculation

---

## Files Changed

### New
- `services.yaml` - Service schema definition for `set_room_temperature`
- `tests/domain/services/test_cop.py` - Unit tests for COP mode filtering (138 lines)

### Modified
- `const.py` - Added `CONF_ENERGY_ENTITY` constant
- `config_flow.py` - Added `energy_entity` field to config flow `POWER_SCHEMA` and options flow `async_step_sensors`
- `entities/base/sensor.py` - Added `_get_energy_value()` method, dispatch in `native_value`, and `source` attribute for `power_consumption`
- `translations/en.json` - Added `energy_entity` labels in config and options steps
- `translations/fr.json` - Added `energy_entity` labels in config and options steps
- `api/modbus/registers/atw_mbs_02.py` - Added `circuit1_current_temp` and `circuit2_current_temp` to `WRITABLE_KEYS`
- `api/base.py` - Added abstract method `set_circuit_room_temperature()`
- `api/modbus/__init__.py` - Implemented `set_circuit_room_temperature()`
- `entities/base/climate.py` - Added `async_set_room_temperature()` handler
- `entities/base/sensor.py` - COP sensors use `operation_state` for mode filtering
- `domain/models/cop.py` - Added `operation_state` field to `COPInput`
- `domain/services/cop.py` - `_is_mode_matching` uses `operation_state` instead of `hvac_action`
- `adapters/storage/recorder_rehydrate.py` - `accepted_operation_states` filter for rehydration
- `climate.py` - Registered entity platform service
- `translations/en.json` - Added `services` section
- `translations/fr.json` - Added `services` section (French)

---

## Installation

### Via HACS (Recommended)

1. Open HACS
2. Go to Integrations
3. Find "Hitachi Yutaki"
4. Click "Update" or "Redownload"
5. Select version `2.0.0-beta.12`
6. Restart Home Assistant

### Manual Installation

1. Download `beta-12` from GitHub
2. Copy `custom_components/hitachi_yutaki/` to your HA config
3. Restart Home Assistant

---

## Upgrade Path

### From Beta.11 → Beta.12

Direct upgrade:
1. Install Beta.12
2. Restart Home Assistant
3. The new service `hitachi_yutaki.set_room_temperature` is immediately available in Developer Tools > Services

---

## Support

- **Issues**: https://github.com/alepee/hass-hitachi_yutaki/issues
- **Discussions**: https://github.com/alepee/hass-hitachi_yutaki/discussions
- **Beta Testing**: https://github.com/alepee/hass-hitachi_yutaki/discussions/117

---

**Last Updated**: 2026-02-07
