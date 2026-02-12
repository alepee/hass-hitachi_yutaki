# Gateway Documentation

This directory contains the register maps and technical documentation for the Modbus gateways supported by this integration.

## Supported Gateways

| Gateway | Integration Key | Document | PDF Source |
|---|---|---|---|
| ATW-MBS-02 | `modbus_atw_mbs_02` | [ATW-MBS-02.md](ATW-MBS-02.md) | `ATW-MBS-02_line_up_2016.pdf`, `ATW-MBS-02_before_line_up_2016.pdf` |
| HC-A(16/64)MB | `modbus_hc_a_mb` | [HC-A-MB.md](HC-A-MB.md) | `HC-A16MB.pdf` |

## Quick Comparison

| Feature | ATW-MBS-02 | HC-A(16/64)MB |
|---|---|---|
| Max units | 1 Yutaki | Up to 64 indoor units |
| Protocol | Modbus RTU + TCP | Modbus RTU + TCP |
| Addressing | Fixed (1000~1231) | `5000 + (unit_id × 200) + offset` |
| Register layout | Single range | CONTROL (50~86) + STATUS (100~192) |
| Heat pump models | S, S Combi, S80, M | S, SC, S80, M, SC Lite, Yutampo, YCC |
| Outdoor unit data | No | Yes |
| YCC support | No | Yes |

## PDF Source Documents

The original Hitachi PDF documentation is stored alongside the markdown files:

- `ATW-MBS-02_before_line_up_2016.pdf` — PMML0419A rev.1 (05/2016), Yutaki series before 2016
- `ATW-MBS-02_line_up_2016.pdf` — PMML0419A rev.1 (05/2016), Yutaki 2016 series
- `HC-A16MB.pdf` — PMML0351A rev.4 (04/2020), HC-A(8/16/64)MB / HC-A64NET series

## Integration Register Mapping

The integration's register map implementations are in:

- `custom_components/hitachi_yutaki/api/modbus/registers/atw_mbs_02.py`
- `custom_components/hitachi_yutaki/api/modbus/registers/hc_a_mb.py`

These files define how the raw Modbus registers documented here are mapped to the integration's internal data model.
