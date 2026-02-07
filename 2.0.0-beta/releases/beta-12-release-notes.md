# Hitachi Yutaki – COP Fix & Room Temperature Service (v2.0.0-beta.12)

[![Downloads for this release](https://img.shields.io/github/downloads/alepee/hass-hitachi_yutaki/v2.0.0-beta.12/total.svg)](https://github.com/alepee/hass-hitachi_yutaki/releases/v2.0.0-beta.12)

This release fixes COP DHW showing identical values to COP Heating (#191) and adds a new `set_room_temperature` service for Modbus thermostat mode.

## ✨ New Features

### `set_room_temperature` Service

When the Modbus thermostat is enabled on a circuit (`switch.thermostat`), the heat pump expects the BMS to push the measured room temperature. Until now, this required direct Modbus writes via the generic integration.

The new `hitachi_yutaki.set_room_temperature` service makes this native:

```yaml
service: hitachi_yutaki.set_room_temperature
target:
  entity_id: climate.hitachi_circuit_1
data:
  temperature: "{{ states('sensor.salon_temperature') }}"
```

**Example automation** — push the warmest room temperature every minute:

```yaml
automation:
  - alias: "Update heat pump room temperature"
    trigger:
      - platform: time_pattern
        minutes: "/1"
    action:
      - service: hitachi_yutaki.set_room_temperature
        target:
          entity_id: climate.hitachi_circuit_1
        data:
          temperature: >
            {{ [states('sensor.salon_temperature'),
                states('sensor.chambre_temperature'),
                states('sensor.bureau_temperature')]
               | map('float', 0) | max }}
```

- Targets circuit climate entities only
- Temperature range: 0–50°C, step 0.1°C
- Writes to Modbus register 1012 (circuit 1) or 1023 (circuit 2)
- Full UI in Developer Tools > Services

## 🐛 Bug Fixes

### COP DHW Identical to COP Heating
**Issue:** [#191](https://github.com/alepee/hass-hitachi_yutaki/issues/191)

Since the v2.0.0 refactoring, COP DHW and COP Heating showed identical values. Mode filtering relied on `hvac_action` which only distinguishes heating from cooling — DHW and pool cycles were never differentiated.

Now all four COP sensors use `operation_state` (Modbus register 1090) to precisely filter by cycle type: heating, cooling, DHW, or pool. The fix applies both to live updates and Recorder rehydration on startup.

## 📦 Installation

1. Update via HACS to v2.0.0-beta.12
2. Restart Home Assistant
3. The service is immediately available — no configuration needed

## ⚠️ Important Notes

- **No migration required** — direct upgrade from any previous beta
- The service writes to the register regardless of thermostat mode. When the thermostat is disabled, the heat pump firmware ignores the value.
- The Modbus thermostat must be enabled on the circuit (`switch.thermostat`) for the value to have any effect on regulation.

## 🐛 Bug Reports

If you encounter issues, please report with:
- Home Assistant version
- Heat pump model and gateway type
- Relevant logs from integration

---

**Full Changelog:** [v2.0.0-beta.11...v2.0.0-beta.12](https://github.com/alepee/hass-hitachi_yutaki/compare/v2.0.0-beta.11...v2.0.0-beta.12)
