# TODO: HC-A(16/64)MB Register Map — Future Work

Based on analysis of Nathan-38's full Modbus scan (issue #96) against the
HC-A16MB documentation (sections 5.2 and 5.3).

## Section 5.3 — Outdoor Unit Registers Not Yet Implemented

Base address: 30000. These registers are shared across all indoor units.

| Offset | Name | Range | Unit | Notes |
|--------|------|-------|------|-------|
| 0 | Outdoor Air Temperature | -50~50 | °C | Duplicate of indoor offset 142 (low priority) |
| 3 | Number of Operating Compressors | 0~16 | — | Scan value: 0 (compressor off at time of scan) |
| 4 | Discharge Pressure | 0.0~5.0 | MPa (×0.1) | Scan value: 16 → 1.6 MPa |
| 5 | Suction Pressure | -0.2~2.0 | MPa (×0.1) | Scan value: 7 → 0.7 MPa |
| 9 | EVO2 / Hot Bypass | 0~100 | % | |
| 10 | EVB | 0~100 | % | |
| 11–17 | Noise/Power Control Registers | — | — | R/W registers for noise and power limits |

## Section 5.2.2 — Indoor Unit Registers Not Yet Implemented

Base address: `5000 + (Modbus_Id × 200) + offset`.

| Offset | Name | Range | Notes |
|--------|------|-------|-------|
| 145 | H-Link Communication State | 0/1/2 | 0=OK, 1=no comm >180s, 2=init |
| 146 | Software PCB Version | — | Scan value: 118 |
| 147 | Software LCD Version | — | Scan value: 127 |
| 148 | Unit Capacity | — | Scan value: 8 |
| 150 | Water Outlet HP (TwoHP) | — | Yutaki S & S Combi only |
| 151 | Ta1av — Outdoor Unit Ambient Average Temperature | — | |
| 152–153 | Ta2 / Ta2av — Second Ambient Temperature | — | Instantaneous / Average |
| 154–155 | O2 / O3 — Water Outlet Temp 2/3 | — | |
| 159 | CD: Capacity Data | — | Scan value: 66 |
| 160 | Mixing Valve Opening | 0~100% | |
| 161 | Defrosting Status | 0/1 | 0=no, 1=defrosting |
| 176 | R134 Te SH | — | S80 only |
| 177 | R134 Secondary Current | — | S80 only |
| 178 | R134 Stop Code | — | S80 only |
| 190–192 | YCC Registers | — | Enabled/Working/Required Units |

## Scan Anomalies / Low-Priority Notes

- **Zone 2000+offset**: HC-A8MB compatible addressing — mirrors indoor unit data.
  Can be ignored for HC-A16/64MB.
- **Zone 20000+offset**: Old gateway compatible addressing — mirrors indoor unit data.
  Can be ignored for HC-A16/64MB.
- **Multi-outdoor-unit support (Ou>0)**: Not yet validated. The outdoor unit base
  address (30000) may need a multiplier for systems with multiple outdoor units.
  Requires hardware testing to confirm.
