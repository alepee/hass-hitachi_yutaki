# Pre-2016 ATW-MBS-02 Gateway Support

**Date:** 2026-03-19
**Issue:** [#248](https://github.com/alepee/hass-hitachi_yutaki/issues/248)
**Branch:** `feat/pre-2016-support`

## Context

The ATW-MBS-02 Modbus gateway has two distinct register maps documented in PMML0419A rev.1 (Section 5.2 and 5.3). The integration currently only supports the Line-up 2016 register map. Gen 1 Yutaki units (S and S Combi with NWE/NWSE suffix, R410A refrigerant) use the Before Line-up 2016 register map, which has different addresses for status, control, and servicing registers.

A user with a RWD-4.0NWSE-260S confirmed via full register scans that their unit uses the Before-2016 map. Using the wrong map causes misread sensors, write errors, and potential alarm codes.

## Design

### 1. New Gateway: `atw-mbs-02-pre2016`

**Integration key:** `modbus_atw_mbs_02_pre2016`

**File:** `api/modbus/registers/atw_mbs_02_pre2016.py`

A new `AtwMbs02Pre2016RegisterMap(HitachiRegisterMap)` class with its own register dictionaries, following the Section 5.2 layout. This is treated as a third gateway type, on the same level as `atw-mbs-02` and `hc-a-mb`.

Key differences from the 2016 map:

| Zone | Before 2016 | 2016 |
|---|---|---|
| Control circuit 1 | addr 1002-1008 | addr 1002-1012 |
| Control circuit 2 | addr 1009-1015 | addr 1013-1023 |
| Control DHW | addr 1016-1017 | addr 1024-1025 |
| Control pool | addr 1018-1019 | addr 1028-1029 |
| Control anti-legionella | addr 1020-1021 | addr 1030-1031 |
| Status operation state | addr 1077 | addr 1090 |
| Status outdoor temp | addr 1078 | addr 1091 |
| Status water inlet | addr 1079 | addr 1092 |
| Status water outlet | addr 1080 | addr 1093 |
| Status DHW temp | addr 1075 | addr 1080 |
| Status system_config | addr 1074 (8 bits) | addr 1089 (12 bits) |
| LCD Central Mode | addr 1073 | addr 1088 |
| Servicing unit_model | addr 1217 (values 0-1) | addr 1218 (values 0-3) |
| Servicing water outlet hp | addr 1199 | addr 1200 |
| Servicing water target | addr 1218 | addr 1219 |
| Unit mode values | 0: Cool, 1: Heat | 0: Cool, 1: Heat, 2: Auto |

Before-2016 does **not** have:
- Auto mode (only Cool/Heat)
- Per-circuit eco mode / eco offset registers
- Per-circuit thermostat available toggle
- Wireless settings bits (system_config bits 8-11)

Before-2016 unit_model values:
- 0: Yutaki S
- 1: Yutaki S Combi

(S80 and M were introduced with the 2016 lineup and are not applicable.)

### 2. Config Flow

The gateway selection step changes from 2 to 3 options:

- ATW-MBS-02 (Line-up 2016)
- **ATW-MBS-02 (Before Line-up 2016)**
- HC-A(16/64)MB

The pre-2016 option includes a description noting this refers to the hardware generation, not the installation date, with a link to the model decoder tool.

The selected gateway is persisted in the config entry as `gateway_type: "modbus_atw_mbs_02_pre2016"`. The rest of the flow (Modbus connection, profile detection) works identically — only the `RegisterMap` instance changes.

Profile detection reads `unit_model` from address 1217 (not 1218) and only matches Yutaki S or Yutaki S Combi profiles.

### 3. Model Decoder Tool

A standalone HTML page served via GitHub Pages to help users identify their hardware generation.

**Location:** `docs/tools/model-decoder.html`

**UX:** Cascading selectors guiding the user through:
1. **Prefix** — `RWD` / `RWM` / `RWH` / `RASM` (determines family)
2. **Capacity** — filtered values for the selected prefix
3. **Suffix** — filtered by prefix (e.g., for RWD: NWE, NWSE, NW1E, RW1E, RW2E, RW3E)
4. **Tank** (RWD only) — -200, -260S, -220S, etc.

The result displays as soon as the suffix is selected: family, generation, refrigerant, applicable register map, and a config flow recommendation.

**Constraints:**
- Zero dependencies (vanilla HTML + CSS + JS)
- Works locally and via GitHub Pages
- Nomenclature data embedded in JS (from `model-nomenclature.md` tables)
- Light branding consistent with the repo

### 4. Scanner Support

The `scan_gateway.py` script gains Before-2016 support:

- **Auto-detection:** if `unit_model` at address 1218 returns a value outside 0-3, probe address 1217. If 0 or 1, detect as `atw-mbs-02-pre2016`.
- **Annotations:** build the lookup table from `AtwMbs02Pre2016RegisterMap` when the detected gateway is before-2016.
- **System recap:** use Before-2016 addresses for outdoor temp (1078), water inlet (1079), operation state (1077), system config (1074), etc.
- **CLI flag:** add `atw-mbs-02-pre2016` as a `--gateway` choice.

### 5. Implementation Phases

#### Phase 1 — Read support (initial PR, validated with tester from #248)

- New register map `atw_mbs_02_pre2016.py` (status + servicing registers)
- Config flow: 3rd gateway choice with help link
- Profile detection adapted (unit_model at 1217, S and S Combi only)
- All read sensors: temperatures, operation state, system status, compressor data, DHW
- Scanner `scan_gateway.py` with before-2016 support
- Model decoder HTML tool (GitHub Pages)
- Unit tests for the new register map

#### Phase 2 — Write support (separate PR, after phase 1 validation)

- Control registers with Before-2016 layout (diverge from addr 1005)
- Climate entity: no Auto mode, only Cool/Heat
- DHW controls (addr 1016-1017 instead of 1024-1025)
- Pool controls (addr 1018-1019 instead of 1028-1029)
- Anti-legionella controls (addr 1020-1021 instead of 1030-1031)
- No eco mode toggle (registers don't exist in before-2016)
- Write tests

## Data Sources

- [PMML0419A rev.1 Section 5.2](../../../docs/gateway/datasheets/ATW-MBS-02_before_line_up_2016.pdf) — Before Line-up 2016 register tables
- [Model Nomenclature](../../reference/model-nomenclature.md) — Hitachi model reference decoding
- [Issue #248 scan results](https://github.com/alepee/hass-hitachi_yutaki/issues/248) — Real-world validation from RWD-4.0NWSE-260S
