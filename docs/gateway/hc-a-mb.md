# HC-A(8/16/64)MB / HC-A64NET — Network / Modbus Gateway Register Map

> Source: PMML0351A rev.4 — 04/2020

## Overview

The HC-A series are network/Modbus gateways designed for Hitachi HVAC systems. They support multiple indoor units and expose control/monitoring registers over Modbus RTU (RS485) or Modbus TCP (Ethernet).

### Models

| Model | Max Indoor Units | Modbus RTU | Modbus TCP | CSNET Manager |
|---|---|---|---|---|
| HC-A8MB | 8 | Yes | Yes | No |
| HC-A16MB | 16 | Yes | Yes | No |
| HC-A64MB | 64 | Yes | Yes | No |
| HC-A64NET | 64 | No | TCP/IP | Yes |

### Classification

- **HC**: Interface Controller Control
- **A**: H-LINK II Compatible
- **8/16/64**: Maximum Number of Controllable Units
- **MB**: Modbus gateway
- **NET**: Gateway for CSNET Manager

### System Compatibility

**HC-A(16/64)MB**: SET FREE, UTOPIA, CENTRIFUGAL and HEATING systems
**HC-A8MB and HC-A64NET**: SET FREE, UTOPIA and CENTRIFUGAL systems

### Incompatibilities

- Centralised remote controls
- Building air conditioning controls (*)
- Other Hitachi BMS Gateways (LONWORKS, BACNET, KNX, FIDELIO)
- Other Hitachi MODBUS Gateways
- Other units of the same model

> (*) HC-A64NET is compatible with CSNET Manager.

## Hardware Specifications

| Item | Specifications |
|---|---|
| Power supply | 1~ 230 V ±10% 50 Hz |
| Consumption | 4.5W (maximum) |
| Outer dimensions | 106 × 90 × 58 mm (W × D × H) |
| Weight | 165 g |
| Ambient temperature | 0~60 °C |
| Humidity | 20~85% (without condensation) |

## Communication

### RS485

| Item | Specifications |
|---|---|
| Type | Modbus RTU for HC-A(8/16/64)MB. Not available for HC-A64NET |
| Connector | Serial Port RS485 (3 screw terminals) |
| Communication line | Shielded twisted pair cable, with third wire (common), with polarity |
| Communication system | Half-duplex, multipoint serial connection |
| Communication method | Non parity or odd/even parity selection. Data length: 8 bits – 1 stop bit |
| Baud rate | 19200/9600 Baud |
| Length | Max. 1200 m (EIA-485) |

### Ethernet

| Item | Specifications |
|---|---|
| Type | Modbus TCP for HC-A(8/16/64)MB. TCP/IP communication for HC-A64NET |
| Connector | Ethernet (RJ45) |
| Communication line | Two twisted pair cable CAT5 or better (T-568A/T-568B) |
| Communication system | Full-duplex |
| Length | Max. 100 m (IEEE 802.3) |

### H-LINK

| Item | Specifications |
|---|---|
| Communication with | See [System Compatibility](#system-compatibility) |
| Communication line | Twisted pair shielded cable, non-polarity |
| Communication system | Half-duplex |
| Communication method | Asynchronous |
| Speed | 9600 Bauds |
| Length of wiring | 1000 m maximum (total length of H-LINK I/O bus) |
| Max gateways | 1 Gateway per H-LINK SYSTEM |

## Electrical Wiring

| Name | Connection | Cable specification |
|---|---|---|
| X1 | Power supply | 0.75 mm² polychloroprene sheathed flexible cord (IEC 57) |
| X3 | Ethernet | Category 5 or higher LAN cables |
| X4 | H-LINK | Twisted pair shielded cable 0.75 mm². Shield grounded one side only |
| X5 | RS485 | 3 cores cable harness 0.75 mm² grounded in one side only |
| X6 | USB | USB Mini-B plug cable (configuration only) |

## DSW Configuration

| Name | Function | Description |
|---|---|---|
| SW1-1 | Configuration | Modbus end resistance (*) |
| SW1-2 | Not used | Keep always ON |

> (*) Not applicable to HC-A64NET.

## Register Addressing

The HC-A series uses offset-based addressing. The actual Modbus register address is calculated as:

```
Address = 5000 + (Modbus_Id × 200) + Offset
```

Where:
- **5000**: Base address (position 20000 also available for backward compatibility)
- **Modbus_Id**: Indoor unit address as configured by configuration software
- **Offset**: Register offset within the unit's address block

### Availability Legend

The register tables include an "Availability" column indicating which system types support each register:

| Code | Description |
|---|---|
| VRF | PAC: VRF and package units |
| RAC | Domestic units connected to H-LINK via PSC-6RAD or SPX-RAMHLK |
| ATW | Air to water units (Yutaki) |

---

## Indoor Units

### Available Data for HC-A(8/16/64)MB

These registers are available for all HC-A gateway models. The register address is: `5000 + (Modbus_Id × 200) + Offset`.

| Offset | Description | Values | R/W |
|---|---|---|---|
| 0 | Exist | 0: No exist, 1: Exist | Read |
| 1 | System address | 0~63 | Read |
| 2 | Unit address | 0~63 | Read |
| 3 | On/Off setting order | 0: Stop, 1: Run | Read/Write |
| 4 | Mode setting order | 0: Cool, 1: Dry, 2: Fan, 3: Heat, 4: Auto | Read/Write |
| 5 | Fan setting order | 0: Low, 1: Medium, 2: High, 3: High2, 4: Auto | Read/Write |
| 6 | Setting temperature | °C (set according to the unit working range) | Read/Write |
| 7 | Louver setting | 0~7 (7 is Auto) | Read/Write |
| 8 | Central setting (*3) | Bit 0: On/Off (always can be stopped), Bit 1: Mode, Bit 2: Setting Temp, Bit 3: Fan, Bit 4: Louver | Read/Write |
| 9 | On/Off status | 0: Off, 1: On | Read |
| 10 | Mode status | 0: Cool, 1: Dry, 2: Fan, 3: Heat, 4: Auto | Read |
| 11 | Fan status | 0: Low, 1: Medium, 2: High, 3: High2, 4: Auto | Read |
| 12 | Setting temperature status | °C (set according to the unit working range) | Read |
| 13 | Louver status | 0~7 (7 is Auto) | Read |
| 14 | (Not used) | — | — |
| 15 | Inlet temperature reading (*2) | -63°C ~ 63°C | Read |
| 16 | Outlet temperature reading (*2) | -63°C ~ 63°C | Read |
| 17 | Gas pipe temperature reading (*2) | -63°C ~ 63°C | Read |
| 18 | Liquid pipe temperature reading (*2) | -63°C ~ 63°C | Read |
| 19 | Alarm code | Alarm unit from 7-segment | Read |
| 20 | Compressor stop cause | (Read unit service manual) | Read |
| 21 | Indoor unit expansion valve opening | 0~100 | Read |
| 22 | Unit operation condition | 0: OFF, 1: Thermo OFF, 2: Thermo ON, 3: Alarm | Read |
| 23 | (Not used) | — | — |
| 24 | Ambient temperature (*2) | -63°C ~ 63°C | Read |
| 25 | Remote control switch temperature (*2) (only when available in the unit) | -63°C ~ 63°C | Read |
| 26 | Remote control switch configuration | b0: 0 Master/1 Slave, b1: 0 with RCS/1 Without RCS | Read/Write |
| 27 | Remote control switch group | 0: No group, 1~255 | Read/Write |
| 28~30 | (Not used) | — | — |
| 31 | Remote sensor temperature (*2) | -63°C ~ 63°C | Read |

### Additional Data for HC-A(16/64)MB

These registers are available only on the HC-A16MB and HC-A64MB models.

| Offset | Description | Values | R/W | VRF | RAC | ATW |
|---|---|---|---|---|---|---|
| 0 | Exist | 0: No exist, 1: Exist | Read | O | O | |
| 1 | System address | H-LINK 1: 0~15, H-LINK 2: 0~63 | Read | O | O | |
| 2 | Unit address | — | Read | O | O | |
| 3 | Type | 0: Indoor Unit | Read | O | O | |
| 4 | On/Off setting order | 0: Stop, 1: Run | Read/Write | O | O | |
| 5 | Mode setting order | 0: Cool, 1: Dry, 2: Fan, 3: Heat, 4: Auto | Read/Write | O | O | |
| 6 | Fan setting order | 0: Low, 1: Medium, 2: High, 3: High2, 4: Auto | Read/Write | O | O | |
| 7 | Setting temperature | °C (set according to unit working range) | Read/Write | O | O | |
| 8 | Temperature setting with 0.5°C intervals | °C × 10 (19.5°C read as 195) | Read/Write | O | | |
| 9 | Heating temperature setting for AUTO Cool/Heat | °C | Read/Write | O | | |
| 10 | Heating Temperature setting for AUTO Cool/heat with 0.5°C intervals | °C × 10 (19.5°C read as 195) | Read/Write | O | | |
| 11 | Cooling Temperature setting for AUTO Cool/heat | °C | Read/Write | O | | |
| 12 | Cooling Temperature setting for AUTO Cool/heat with 0.5°C intervals | °C × 10 (19.5°C read as 195) | Read/Write | O | | |
| 13 | Louver setting | 0~7 (7 is Auto) | Read/Write | O | | |
| 14 | Central setting (*2) | Bit 0: On/Off, Bit 1: Mode, Bit 2: Setting Temp, Bit 3: Fan, Bit 4: Louver | Read/Write | O | O | |
| 15 | On/Off status | 0: Off, 1: On | Read | O | O | |
| 16 | Mode status | 0: Cool, 1: Dry, 2: Fan, 3: Heat, 4: Auto | Read | O | O | |
| 17 | Fan status | 0: Low, 1: Medium, 2: High, 3: High2, 4: Auto | Read | O | O | |
| 18 | Setting temperature status | °C (set according to unit working range) | Read | O | O | |
| 19 | Temperature setting with 0.5°C intervals status | °C × 10 (19.5°C read as 195) | Read | O | | |
| 20 | Heating temperature setting for AUTO Cool/Heat status | °C | Read | O | | |
| 21 | Heating Temperature setting for AUTO Cool/heat with 0.5°C intervals status | °C × 10 (19.5°C read as 195) | Read | O | | |
| 22 | Cooling Temperature setting for AUTO Cool/heat status | °C | Read | O | | |
| 23 | Cooling Temperature setting for AUTO Cool/heat with 0.5°C intervals status | °C × 10 (19.5°C read as 195) | Read | O | | |
| 24 | Louver status | 0~7 (7 is Auto) | Read | O | | |
| 25 | Air inlet temperature reading (*2) | -63°C ~ 63°C | Read | O | | |
| 26 | Air outlet temperature reading (*2) | -63°C ~ 63°C | Read | O | | |
| 27 | Gas pipe temperature reading (*2) | -63°C ~ 63°C | Read | O | | |
| 28 | Liquid pipe temperature reading (*2) | -63°C ~ 63°C | Read | O | | |
| 29 | Alarm code | Alarm unit from 7-segment | Read | O | O(1) | |
| 30 | Compressor stop cause | (Read unit service manual) | Read | O | | |
| 31 | Indoor unit expansion valve opening | 0~100 | Read | O | | |
| 32 | Unit operation condition | 0: OFF, 1: Thermo OFF, 2: Thermo ON, 3: Alarm | Read | O | O | |
| 33 | Remote temperature sensor (THM4) value (*2) | -63°C ~ 63°C | Read | O | | |
| 34 | Remote control switch temperature (*2) (only when available in the unit) | -63°C ~ 63°C | Read | O | O | |
| 35 | Remote control switch configuration | b0: 0 Master/1 Slave, b1: 0 with RCS/1 Without RCS | Read/Write | O | | |
| 36 | Remote control switch group | 0: No group, 1~255 | Read/Write | O | | |
| 37 | CN3 Configuration status | b0: Input 1 open/close, b1: Input 2 open/close, b2: Enabled/Disabled | Read | O | | |
| 38~49 | Reserved | — | — | | | |

---

## ATW (Air-to-Water) Registers — HC-A(16/64)MB

These registers are specific to Yutaki air-to-water heat pumps connected via the HC-A(16/64)MB gateway.

### Control Registers (Read/Write)

| Offset | Description | Values | R/W | ATW |
|---|---|---|---|---|
| 50 | Control Unit Run/Stop | 0: Stop, 1: Run | Read/Write | O |
| 51 | Control Unit Mode | 0: Cool, 1: Heat | Read/Write | O |
| 52 | Control Circuit 1 Run/Stop | 0: Stop, 1: Run | Read/Write | O |
| 53 | Control Heat. OTC Zone 1 | 0: No, 1: Points, 2: Gradient, 3: Fix | Read/Write | O |
| 54 | Control Cool. OTC 1 | 0: No, 1: Points, 2: Fix | Read/Write | O |
| 55 | Control Circuit 1: Water heating Fix Setting Temp | 0~80 | Read/Write | O |
| 56 | Control Circuit 1: Water cooling Fix Setting Temp | 0~80 | Read/Write | O |
| 57 | Control Circuit 1: Eco mode | 0: ECO, 1: Comfort | Read/Write | O |
| 58 | Control Circuit 1: Heat ECO Offset Temperature | 1~10 | Read/Write | O |
| 59 | Control Circuit 1: Cool ECO Offset Temperature | 1~10 | Read/Write | O |
| 60 | Control Circuit 1: External MBS/KNX Thermostat Available | 0: Not Available, 1: Available | Read/Write | O |
| 61 | Control Zone 1: Thermostat Setting | 0~65535 | Read/Write | O |
| 62 | Control Zone 1: Room Ambient Temperature | -32667~32667 | Read/Write | O |
| 63 | Control Circuit 2 Run/Stop | 0: Stop, 1: Run | Read/Write | O |
| 64 | Control Heat. OTC Zone 2 | 0: No, 1: Points, 2: Gradient, 3: Fix | Read/Write | O |
| 65 | Control Cool. OTC 2 | 0: No, 1: Points, 2: Fix | Read/Write | O |
| 66 | Control Circuit 2: Water heating Fix Setting Temp | 0~80 | Read/Write | O |
| 67 | Control Circuit 2: Water cooling Fix Setting Temp | 0~80 | Read/Write | O |
| 68 | Control Circuit 2: Eco mode | 0: ECO, 1: Comfort | Read/Write | O |
| 69 | Control Circuit 2: Heat ECO Offset Temperature | 1~10 | Read/Write | O |
| 70 | Control Circuit 2: Cool ECO Offset Temperature | 1~10 | Read/Write | O |
| 71 | Control Circuit 2: External MBS/KNX Thermostat Available | 0: Not Available, 1: Available | Read/Write | O |
| 72 | Control Zone 2: Thermostat Setting | 0~65535 | Read/Write | O |
| 73 | Control Zone 2: Room Ambient Temperature | -32667~32667 | Read/Write | O |
| 74 | Control DHWT Run/Stop | 0: Stop, 1: Run | Read/Write | O |
| 75 | Control DHWT Setting Temperature | 0~80 | Read/Write | O |
| 76 | Control DHW Boost | 0: No request, 1: Request | Read/Write | O |
| 77 | Reserved | — | — | |
| 78 | Control DHW Demand Mode | 0: Standard, 1: High demand | Read/Write | O |
| 79 | Control Swimming Pool Run/Stop | 0: Stop, 1: Run | Read/Write | O |
| 80 | Control Swimming Pool Setting Temperature | 0~80 | Read/Write | O |
| 81 | Control AntiLegionella Run/Stop | 0: Stop, 1: Run | Read/Write | O |
| 82 | Control AntiLegionella Setting Temperature | 0~80 | Read/Write | O |
| 83 | Control Block menu | 0: No, 1: Block (user cannot access the menu) | Read/Write | O |
| 84 | Control Yutaki Forced OFF | 0: Normal Operation, 1: Forced OFF | Read/Write | O |
| 85 | Space Heating Heater Forced OFF | 0: Normal Operation, 1: Heater Forced OFF | Read/Write | O |
| 86 | Control Communication Alarm bit | 0: No, 1: Alarm | Read/Write | O |
| 87~99 | Reserved | — | — | |

### Status Registers (Read)

| Offset | Description | Values | R/W | ATW |
|---|---|---|---|---|
| 100 | Status Unit Run/Stop | 0: Stop, 1: Run | Read | O |
| 101 | Status Mode | B0: 0: Cool / 1: Heat, B1: 0: Normal / 1: Auto | Read | O |
| 102 | Status Circuit 1 Run/Stop | 0: Stop, 1: Run | Read | O |
| 103 | Status Heat. OTC 1 | 0: No, 1: Points, 2: Gradient, 3: Fix | Read | O |
| 104 | Status Cool. OTC 1 | 0: No, 1: Points, 2: Fix | Read | O |
| 105 | Status Circuit 1: Water heating Fix Setting Temp | 0~80 | Read | O |
| 106 | Status Circuit 1: Water cooling Fix Setting Temp | 0~80 | Read | O |
| 107 | Status Circuit 1: Eco mode | 0: ECO, 1: Comfort | Read | O |
| 108 | Status Circuit 1: Heat ECO Offset Temperature | 1~10 | Read | O |
| 109 | Status Circuit 1: Cool ECO Offset Temperature | 1~10 | Read | O |
| 110 | Status Circuit 1: Thermostat Setting Temperature | 50~350 (5.0~35.0) | Read | O |
| 111 | Status Circuit 1: Thermostat Room Temperature | 0~1000 (0.0~100.0) | Read | O |
| 112 | Status Circuit 1: Wireless Setting Temperature | 50~350 (5.0~35.0) | Read | O |
| 113 | Status Circuit 1: Wireless Room Temperature | 0~1000 (0.0~100.0) | Read | O |
| 114 | Status Circuit 2 Run/Stop | 0: Stop, 1: Run | Read | O |
| 115 | Status Heating OTC 2 | 0: No, 1: Points, 2: Gradient, 3: Fix | Read | O |
| 116 | Status Cooling OTC 2 | 0: No, 1: Points, 2: Fix | Read | O |
| 117 | Status Circuit 2: Water heating Fix Setting Temp | 0~80 | Read | O |
| 118 | Status Circuit 2: Water cooling Fix Setting Temp | 0~80 | Read | O |
| 119 | Status Circuit 2: Eco mode | 0: ECO, 1: Comfort | Read | O |
| 120 | Status Circuit 1: Heat ECO Offset Temperature | 1~10 | Read | O |
| 121 | Status Circuit 1: Cool ECO Offset Temperature | 1~10 | Read | O |
| 122 | Status Zone 2: Thermostat Setting | 50~350 (5.0~35.0) | Read | O |
| 123 | Status Zone 2: Ambient Temperature | 0~1000 (0.0~100.0) | Read | O |
| 124 | Status Circuit 2: Wireless Setting Temperature | 50~350 (5.0~35.0) | Read | O |
| 125 | Status Circuit 2: Wireless Room Temperature | 0~1000 (0.0~100.0) | Read | O |
| 126 | Status DHWT Run/Stop | 0: Stop, 1: Run | Read | O |
| 127 | Status DHWT Setting Temperature | 0~80 | Read | O |
| 128 | Status DHW Boost | 0: Disable, 1: Enable | Read | O |
| 129 | Reserved | — | — | |
| 130 | Status DHW Demand Mode | 0: Standard, 1: High demand | Read | O |
| 131 | Status DHW Temperature | -80~100 | Read | O |
| 132 | Status Swim.Pool Run/Stop | 0: Stop, 1: Run | Read | O |
| 133 | Status Swim. Pool Setting Temperature | 0~80 | Read | O |
| 134 | Status Swim. Pool Temperature | -80~100 | Read | O |
| 135 | Status AntiLeg. Run/Stop | 0: Stop, 1: Run | Read | O |
| 136 | Status AntiLeg. Setting Temperature | 0~80 | Read | O |
| 137 | Status block menu | 0: No, 1: Block | Read | O |
| 138 | Status Communication Alarm bit | 0: No, 1: Alarm | Read | O |
| 139 | LCD Central Mode | 0: Local, 1: Air (not for Yutampo), 2: Water (not for Yutampo), 3: Full | Read | O |
| 140 | System Configuration | See [System Configuration Bits](#system-configuration-bits) | Read | O |
| 141 | Operation State | See [Operation State Values](#operation-state-values) | Read | O |
| 142 | Outdoor Ambient T° | -80~100 | Read | O |
| 143 | Water Inlet T° | -80~100 | Read | O |
| 144 | Water outlet T° | -80~100 | Read | O |
| 145 | H-Link Communication State | See [H-LINK State Values](#h-link-communication-state-values) | Read | O |
| 146 | Software PCB | — | Read | O |
| 147 | Software LCD | — | Read | O |
| 148 | Unit Capacity | — | Read | O |
| 149 | Unit Power Consumption | — | Read | O |
| 150 | Water Outlet HP (TwoHP) | 0~100 (Yutaki S & S Combi only) | Read | O |
| 151 | Ta1av: Outdoor Unit Ambient Average Temperature | -80~100 | Read | O |
| 152 | Ta2: Second Ambient Temperature (inst) | -80~100 | Read | O |
| 153 | Ta2av: Second Ambient Temperature (avg) | -80~100 | Read | O |
| 154 | O2: Water outlet Temp 2 (Two2) | -80~100 | Read | O |
| 155 | O3: Water outlet Temp 3 (Two3) | -80~100 | Read | O |
| 156 | Tg: Gas Temperature (THMg) | -80~100 | Read | O |
| 157 | TI: Liquid Temperature (THMI) | -80~100 | Read | O |
| 158 | EVI: Indoor expansion valve opening | 0~100 | Read | O |
| 159 | CD: Capacity Data | — | Read | O |
| 160 | Mixing Valve Opening | 0~100 | Read | O |
| 161 | Defrosting | 0: No defrosting, 1: Defrosting | Read | O |
| 162 | Unit Model | See [Unit Model Values](#unit-model-values) | Read | O |
| 163 | Th: Water Temp Setting (Ttwo) | -80~100 | Read | O |
| 164 | Water Flow | Water Flow [0.1 m³/h] | Read | O |
| 165 | Pump Speed | 0~100 | Read | O |
| 166 | System status 2 | See [System Status 2 Bits](#system-status-2-bits) | Read | O |
| 167 | Alarm number | 0: Alarm, XXX: Alarm number | Read | O |

### R134a Secondary Compressor (Yutaki S80 only)

| Offset | Description | R/W | ATW |
|---|---|---|---|
| 168 | R134a Discharge Temperature | Read | O |
| 169 | R134a Suction temperature | Read | O |
| 170 | R134a Discharge Pressure | Read | O |
| 171 | R134a Suction pressure | Read | O |
| 172 | R134a Compressor frequency | Read | O |
| 173 | R134a Indoor Expansion valve opening | Read | O |
| 174 | R134a Compressor current value | Read | O |
| 175 | R134a Retry Code | Read | O |
| 176 | R134 Te SH | Read | O |
| 177 | R134 Secondary Current | Read | O |
| 178 | R134 Stop Code | Read | O |

### YCC Registers

| Offset | Description | Values | R/W | ATW |
|---|---|---|---|---|
| 179~189 | Reserved | — | — | |
| 190 | YCC - Enabled Units | 0~8 | Read | O |
| 191 | YCC - Working Units | 0~8 | Read | O |
| 192 | YCC - Required Units | 0~8 | Read | O |

---

## Reference Values

### Unit Model Values

Offset 162:

| Value | Description |
|---|---|
| 0 | Yutaki S |
| 1 | Yutaki SC |
| 2 | Yutaki S80 |
| 3 | Yutaki M |
| 4 | Yutaki SC Lite (New) |
| 5 | Yutampo (New) |
| 6 | YCC (New) |

### System Configuration Bits

Offset 140:

| Bit | Description |
|---|---|
| 0 | Zone 1 Heating Available |
| 1 | Zone 2 Heating Available |
| 2 | Zone 1 Cooling Available |
| 3 | Zone 2 Cooling Available |
| 4 | DHWT Available |
| 5 | SWP Available |
| 6 | Room thermostat available Zone 1 |
| 7 | Room thermostat available Zone 2 |
| 8 | Wireless Setting C1 |
| 9 | Wireless Setting C2 |
| 10 | Wireless Room Temperature C1 |
| 11 | Wireless Room Temperature C2 |
| 12 | Slave Unit |

### System Status 2 Bits

Offset 166:

| Bit | Description |
|---|---|
| 0 | Defrost |
| 1 | Solar |
| 2 | Water Pump 1 |
| 3 | Water Pump 2 |
| 4 | Water Pump 3 |
| 5 | Compressor ON |
| 6 | Boiler ON |
| 7 | DHW Heater |
| 8 | Space Heater |
| 9 | Smart function input enabled |
| 10 | Forced OFF |
| 11 | DHW recirculation Pump State |
| 12 | Solar Pump Output State |

### Operation State Values

Offset 141:

| Value | Description |
|---|---|
| 0 | OFF |
| 1 | Cool Demand–OFF |
| 2 | Cool Thermo-OFF |
| 3 | Cool Thermo-ON |
| 4 | Heat Demand-OFF |
| 5 | Heat Thermo-OFF |
| 6 | Heat Thermo-ON |
| 7 | DHW-OFF |
| 8 | DHW-ON |
| 9 | SWP-OFF |
| 10 | SWP-ON |
| 11 | Alarm |

### Status Mode Encoding

Offset 101 uses a bitmask encoding:

| Bit | Value | Description |
|---|---|---|
| B0 | 0 | Cool |
| B0 | 1 | Heat |
| B1 | 0 | Normal |
| B1 | 1 | Auto |

Decoded combinations:
- `0b00` (0) = Cool
- `0b01` (1) = Heat
- `0b10` (2) = Cool Auto (invalid for ATW)
- `0b11` (3) = Heat Auto → Auto mode

### H-LINK Communication State Values

Offset 145:

| Value | Description |
|---|---|
| 0 | No alarm |
| 1 | No communication with RCS or Yutaki unit during more than 180 seconds |
| 2 | Data initialization |

---

## Outdoor Units

Some state registers about outdoor unit have been added. Using these registers it is now possible to know the status of the refrigerant cycle. Some control registers have also been added.

The register address for outdoor units is calculated the same way: `5000 + (Modbus_Id × 200) + Offset`.

| Offset | Description | Values | R/W |
|---|---|---|---|
| 0 | Outdoor Air Temperature | -63°C ~ 63°C | Read |
| 1 | Compressor Discharge Temperature | 0~200 °C | Read |
| 2 | Heating Evaporating Temperature | — | Read |
| 3 | Number of operating Compressor | — | Read |
| 4 | Discharge Pressure | 0.0~5.0 MPa (0.1 MPa) | Read |
| 5 | Suction Pressure | -0.2~2.0 MPa (0.1 MPa or 0.01 MPa depending unit) | Read |
| 6 | Total Current | 0~255 A | Read |
| 7 | Total Real Frequency | 0~255 Hz | Read |
| 8 | EVO1 | 0~100 % | Read |
| 9 | EVO2 / Hot Bypass | 0~100 % | Read |
| 10 | EVB | 0~100 % | Read |
| 11 | Outdoor Unit Option Enabled | 0: Disable, 1: Enable | Read/Write |
| 12 | Noise Control Enabled | 0: Disable, 1: Enable | Read/Write |
| 13 | Noise Control Level Set | 0~9 (see service manual) | Read/Write |
| 14 | Power Control Enabled | 0: Disable, 1: Enable | Read/Write |
| 15 | Power Level | 0~100% | Read/Write |
| 16 | Power Level Set | 0~100% | Read |
| 17 | Power Level Current Value | 0~100% | Read |

---

## Key Differences vs ATW-MBS-02

| Feature | ATW-MBS-02 | HC-A(16/64)MB |
|---|---|---|
| **Addressing** | Fixed registers 1000~1231 | Unit ID-aware: `5000 + (Modbus_Id × 200) + offset` |
| **Register Layout** | Single continuous range | Separate CONTROL (offsets 50~86) and STATUS (offsets 100~192) blocks |
| **Unit Mode (status)** | Direct value: 0=Cool, 1=Heat | Bitmask: B0=Cool/Heat, B1=Normal/Auto |
| **Unit Mode (control)** | 0=Cool, 1=Heat, 2=Auto | 0=Cool, 1=Heat (no Auto in control) |
| **Pool Target Temp** | Stored in tenths of °C (÷10) | Integer °C |
| **OTC Cooling options** | 4 options (No, Points, Gradient, Fix) | 3 options (No, Points, Fix) — no Gradient |
| **Compressor data** | Full set (8 primary registers) | Limited indoor unit block (3 registers) |
| **Status bits** | 10 bits (0x0001~0x0200) | 13 bits (0x0001~0x1000) with 3 extra |
| **Extra status bits** | — | Forced OFF (b10), DHW recirculation (b11), Solar Pump (b12) |
| **Models supported** | 4 (S, S Combi, S80, M) | 7 (+ SC Lite, Yutampo, YCC) |
| **Max units** | 1 Yutaki per gateway | Up to 64 indoor units |
| **Extra controls** | — | Forced OFF, Space Heater Forced OFF |
| **YCC support** | No | Yes (offsets 190~192) |
| **Outdoor unit registers** | No | Yes (separate outdoor unit block) |
| **System Config bits** | 12 bits | 13 bits (adds Slave Unit) |

---

## Notes

- **(1)** Register address is calculated as: `5000 + (Modbus_Id × 200) + Offset` where Modbus_Id is configured by configuration software.
- **(2)** These numbers refer to signed 16-bit value using 2-complement format for negative values.
- **(3)** Bit 0 (ON/OFF) and Bit 4 (Louver) selectable only when all centrals are activated.
- In order to full lock setting from RCS (Central shown in RCS) set register 8/14 to 31.
- For VRF / Package units, only the relevant data are available (heating units registers will not give any value). The situation is the same for heating units.
