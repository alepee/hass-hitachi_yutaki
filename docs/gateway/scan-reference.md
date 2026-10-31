# Modbus Scan Reference — Hitachi ATW Gateways

Reference for interpreting `scan_gateway.py` output and identifying interesting registers when mapping a new gateway or model.

## Quick Start

```bash
make scan                                         # targeted scan (known zones, ~1s)
make scan SCAN_ARGS="--range full"                # FC3+FC4 0-65535 (~45s)
make scan SCAN_ARGS="--range exhaustive"          # FC1-FC4 0-65535 (~3min)
make scan SCAN_ARGS="--range full" > scan.txt     # save to file (progress on stderr)
make scan SCAN_ARGS="--host 192.168.0.4 --gateway hc-a-mb" > scan.txt  # HC-A(16/64)MB, incl. unit table
```

## ATW-MBS-02 Register Map

### Input Registers (FC4) — Read-only hardware identifiers

| Address | Description | Notes |
|---------|-------------|-------|
| 0-2 | Hardware version triplet | e.g. `3846.103.56` |
| 6 | Hardware revision | |
| 8, 16 | Serial number fragments | 16-bit words, same value = same unit |
| 10-11 | Production date | Encoded |
| 12 | Firmware version | |
| 14 | Sensor status | `0xFFFF` = error/disconnected |
| 15, 19 | Configuration flags | |
| 20-32 | Network config | IP address octets (20=192, 21=168, 23=4), port (24=502), mask, gateway |
| 34 | Scan interval | |
| 38 | Connection status | `0xFFFF` = not connected |
| 39 | Gateway type? | `3` observed for ATW-MBS-02 (scan observation only — not read by the integration; gateway detection uses the `unit_model` holding register instead) |
| 40-46 | Device identifiers | Serial numbers, MAC-like values |
| 50-63 | Extended network config | IP pairs (high/low words), alternate interfaces |
| 70-72 | Protocol version | |
| 73-79 | Capability flags | `254` (0xFE) = supported |
| 80-99 | Reserved | Typically `0xFFFF` |

### Holding Registers (FC3) — CONTROL (1000-1031) and STATUS (1080-1231)

#### Control Zone (1000-1049)

| Address | Register | Known | Notes |
|---------|----------|-------|-------|
| 1000 | `unit_power` | Yes | 0=off, 1=on |
| 1001 | `unit_mode` | Yes | 0=cool, 1=heat, 2=auto |
| 1002 | `circuit1_power` | Yes | |
| 1003-1012 | Circuit 1 config | Yes | OTC, eco, target/current temp |
| 1013 | `circuit2_power` | Yes | |
| 1014-1023 | Circuit 2 config | Yes | Same structure as circuit 1 |
| 1024-1027 | DHW config | Yes | power, target, boost, high_demand |
| 1028-1029 | Pool config | Yes | power, target_temp |
| 1030-1031 | Anti-legionella | Yes | enable, temp |
| 1032-1049 | **Unknown** | No | Likely reserved or extended settings |

#### Mirror Zone (1050-1079) — Interesting for discovery

| Address | Observation | Hypothesis |
|---------|-------------|------------|
| 1051 | Mirrors 1001 (unit_mode) | STATUS echo of CONTROL? |
| 1053 | Mirrors 1003 | |
| 1055-1063 | Mirrors 1005-1012 | Circuit 1 status readback |
| 1067-1071 | Mirrors 1016-1020 | Circuit 2 status readback |
| 1077 | Mirrors 1025 (dhw_target) | DHW status readback |
| 1082 | Mirrors 1029 (pool_target) | Pool status readback |

> **Note**: The 1050-1079 zone appears to be a STATUS readback of CONTROL registers. Same values, offset +50. This is undocumented in the ATW-MBS-02 manual but consistently observed.

#### Status Zone (1080-1099)

| Address | Register | Known | Notes |
|---------|----------|-------|-------|
| 1080 | `dhw_current_temp` | Yes | Signed 16-bit. `0xFFBD` = -67 = sensor not connected |
| 1083 | `pool_current_temp` | Yes | Signed 16-bit. `0xFF81` = -127 = sensor not connected |
| 1084-1085 | Anti-legionella status | Yes | |
| 1088 | `central_control_mode` | Yes | |
| 1089 | `system_config` | Yes | **Key register** — see bitmask below |
| 1090 | `operation_state` | Yes | See state table below |
| 1091 | `outdoor_temp` | Yes | Signed 16-bit |
| 1092 | `water_inlet_temp` | Yes | Signed 16-bit |
| 1093 | `water_outlet_temp` (fallback) | Yes | Signed 16-bit. Fallback only — the `water_outlet_temp` key primarily reads register 1200 (HP-level outlet, correct for all modes including DHW/pool) and falls back to 1093 only if 1200 is unavailable |
| 1094 | `system_state` | Yes | 0=sync, 1=desync, 2=init |
| 1095 | `software_pcb` | Yes | Unit board software number, decimal (e.g. 289 on a Yutaki S, shown as "Indoor PCB firmware H-0289" on the LCD); part of the Control Unit device `sw_version` |
| 1096 | `software_lcd` | Yes | Controller (LCD) software number, decimal (e.g. 272 on a Yutaki S, shown as "Controller firmware H-0272" on the LCD); part of the Control Unit device `sw_version` |
| 1097 | Unit Capacity | No | Documented "0~255 kWh". The controller's cumulative capacity (estimated heat output) in whole kWh, wrapping at 255: on a Yutaki S Combi it followed the LCD's "Capacity (Total)" step for step, on an 8 HP Yutaki S its steps did not match the integration's thermal energy. Not usable as a sensor (discussion #503) |
| 1098 | Unit Power consumption | No | Documented "0~255 kWh". An 8-bit electricity counter that stays constant on many units (no input measurement) and has been seen going backwards. Not usable, no longer read (discussion #503) |
| 1099 | **Unknown** | No | Non-zero, constant 63 on both a Yutaki S and a Yutaki S80 (discussion #503) |

#### Compressor Zone (1200-1231)

| Address | Register | Known | Notes |
|---------|----------|-------|-------|
| 1200 | `water_outlet_temp` | Yes | HP-level outlet (primary source for the `water_outlet_temp` key) |
| 1201-1203 | **Unknown** | No | Pre-compressor data. Often `0xFF81` (signed -127 = N/A) |
| 1204-1205 | `water_outlet_2_temp` / `water_outlet_3_temp` | Yes | -127 sentinel = N/A |
| 1206 | `compressor_tg_gas_temp` | Yes | |
| 1207 | `compressor_ti_liquid_temp` | Yes | |
| 1208 | `compressor_td_discharge_temp` | Yes | |
| 1209 | `compressor_te_evaporator_temp` | Yes | |
| 1210 | `compressor_evi_indoor_expansion_valve_opening` | Yes | |
| 1211 | `compressor_evo_outdoor_expansion_valve_opening` | Yes | |
| 1212 | `compressor_frequency` | Yes | |
| 1214 | `compressor_current` | Yes | |
| 1215 | CD: Capacity data | No | Documented row, encoding unknown; non-zero when compressor runs (40 observed) |
| 1216 | `circuit2_mixing_valve_position` | Yes | "MVP: Mixing valve position", %, circuit 2 only; 0xFFFF filtered |
| 1218 | `unit_model` | Yes | **Key register** — 0=S, 1=S Combi, 2=S80, 3=M |
| 1219 | `water_target_temp` | Yes | |
| 1220 | `water_flow` | Yes | Tenths (÷10) |
| 1221 | `pump_speed` | Yes | |
| 1222 | `system_status` | Yes | **Key register** — bitmask, see below |
| 1223 | `alarm_code` | Yes | |
| 1224-1231 | Secondary compressor | Yes | S80 only: discharge temp, suction temp, discharge pressure, suction pressure, frequency, valve opening, current, retry code (1231) |

## HC-A(16/64)MB Register Map

Base address = `5000 + (unit_id * 200)`

### Offsets

| Offset | Zone | Description |
|--------|------|-------------|
| 50-86 | CONTROL (R/W) | Commands to heat pump |
| 100-192 | STATUS (R) | Actual state readback (highest offset actually used is 175) |

Outdoor-unit registers do **not** sit within the `5000 + unit_id*200` indoor base. They are keyed on the unit's outdoor refrigerant cycle, read from the unit table below: base **`30000 + cycle * 100`** (#353), e.g. offset 1 compressor discharge temp, 2 evaporator temp, 6 current, 7 frequency, 8 outdoor EVO valve.

### Unit table (FC4 200+)

The gateway lists the H-LINK units it enumerated in input registers starting at **200**, 4 registers per slot (`200 + slot * 4`), 16 slots on an HC-A16MB and 64 on an HC-A64MB. The targeted scan reads slots 0-15 and prints them decoded in a `UNIT TABLE` section.

| Offset | Content |
|--------|---------|
| +0 | presence flag: `1` on an occupied slot, `0` on an empty one |
| +1 | `Ou`, outdoor refrigerant cycle (keys the outdoor block); `0xFF` = empty slot |
| +2 | `Iu`, indoor unit address (equals `Ou` on a Yutaki S, `Ou + 1` on a monobloc Yutampo); `0xFF` = empty slot |
| +3 | slot index on occupied slots (keys the indoor block); `0xFF` on an empty slot |

An empty slot reads `0 / 255 / 255 / 255`. Any other combination on a slot that is not fully occupied (presence flag set on a cleared slot, a stale `Ou`/`Iu`, a slot index that does not match) is a record the gateway has not finished writing while it re-enumerates the bus.

The slot index is **not a stable identity** (#476). The gateway lists the units sorted by H-LINK address and packs them from slot 0, so a unit missing at enumeration (powered off, disconnected) shifts every unit with a higher address down by one slot. The integration therefore identifies a unit by its `(Ou, Iu)` pair and looks its slot up in the table at every setup.

### Key STATUS offsets

| Offset | Register | ATW-MBS-02 equivalent |
|--------|----------|----------------------|
| 100 | `unit_power` | 1000 |
| 101 | `unit_mode` (bitmask) | 1001 |
| 139 | `central_control_mode` | 1088 |
| 140 | `system_config` | 1089 |
| 141 | `operation_state` | 1090 |
| 142 | `outdoor_temp` | 1091 |
| 143 | `water_inlet_temp` | 1092 |
| 144 | `water_outlet_temp` | 1093 |
| 145 | `system_state` | 1094 |
| 146 | `software_pcb` | 1095 |
| 147 | `software_lcd` | 1096 |
| 160 | `circuit2_mixing_valve_position` | 1216 |
| 162 | `unit_model` | 1218 |
| 163 | `water_target_temp` | 1219 |
| 164 | `water_flow` | 1220 |
| 165 | `pump_speed` | 1221 |
| 166 | `system_status` | 1222 |
| 167 | `alarm_code` | 1223 |
| 168-175 | Secondary compressor | 1224-1231 |

## Key Bitmasks

### system_config (ATW: 1089, HC: offset 140)

| Bit | Mask | Feature |
|-----|------|---------|
| 0 | 0x0001 | Circuit 1 Heating |
| 1 | 0x0002 | Circuit 2 Heating |
| 2 | 0x0004 | Circuit 1 Cooling |
| 3 | 0x0008 | Circuit 2 Cooling |
| 4 | 0x0010 | DHW |
| 5 | 0x0020 | Pool |
| 6 | 0x0040 | Circuit 1 Thermostat |
| 7 | 0x0080 | Circuit 2 Thermostat |
| 8 | 0x0100 | Circuit 1 Wireless |
| 9 | 0x0200 | Circuit 2 Wireless |
| 10 | 0x0400 | Circuit 1 Wireless Temp |
| 11 | 0x0800 | Circuit 2 Wireless Temp |

Example: `0x05C1` = Circuit 1 Heating + Circuit 1 Thermostat + Circuit 2 Thermostat + Circuit 1 Wireless + Circuit 1 Wireless Temp

### system_status (ATW: 1222, HC: offset 166)

| Bit | Mask | Feature |
|-----|------|---------|
| 0 | 0x0001 | Defrost active |
| 1 | 0x0002 | Solar active |
| 2 | 0x0004 | Pump 1 running |
| 3 | 0x0008 | Pump 2 running |
| 4 | 0x0010 | Pump 3 running |
| 5 | 0x0020 | Compressor running |
| 6 | 0x0040 | Boiler active |
| 7 | 0x0080 | DHW heater active |
| 8 | 0x0100 | Space heater active |
| 9 | 0x0200 | Smart function active |

HC-A-MB extensions (bits 10-12):

| Bit | Mask | Feature |
|-----|------|---------|
| 10 | 0x0400 | Forced off |
| 11 | 0x0800 | DHW recirculation |
| 12 | 0x1000 | Solar pump |

### operation_state (ATW: 1090, HC: offset 141)

| Value | State |
|-------|-------|
| 0 | Off |
| 1 | Cool (demand off) |
| 2 | Cool (thermo off) |
| 3 | Cool (thermo on) |
| 4 | Heat (demand off) |
| 5 | Heat (thermo off) |
| 6 | Heat (thermo on) |
| 7 | DHW (off) |
| 8 | DHW (on) |
| 9 | Pool (off) |
| 10 | Pool (on) |
| 11 | Alarm |

## Sentinel Values

| Value | Hex | Meaning |
|-------|-----|---------|
| 0xFFFF | 65535 | Not connected / sensor error / unused register |
| 0xFF81 | 65409 | Signed -127 — sensor not connected (temperature registers) |
| 0xFFBD | 65469 | Signed -67 — sensor not connected (DHW temp) |

## Discovery Checklist

When scanning a new model or gateway, focus on:

1. **Identity**: Input registers 0-12 (HW version, serial, firmware)
2. **Gateway type**: holding 1218/offset 162 (unit_model) — this is what the integration actually uses for detection. Input register 39 shows `3` in scans but is not read by the code.
3. **System config**: Holding 1089/offset 140 — determines available features
4. **Mirror zone**: 1050-1079 — undocumented STATUS readback of CONTROL zone
5. **Unknown non-zero**: registers 1099, 1201-1203, 1215 — candidates for new mappings (1095/1096 = software numbers and 1200/1204/1205 = water outlet temps are already mapped; 1097/1098 are 8-bit kWh counters judged unusable)
6. **Full scan differences**: run `--range full`, diff against this reference to spot new registers
