# ATW-MBS-02 — Modbus Gateway Register Map

> Source: PMML0419A rev.1 — 05/2016
> Product code: 7E549924

## Overview

The ATW-MBS-02 is a Modbus gateway designed for Hitachi air-to-water heat pumps (Yutaki series). It connects to the heat pump via the H-LINK bus and exposes control and monitoring registers over Modbus RTU (RS485) or Modbus TCP (Ethernet).

### Compatibility

- Yutaki S
- Yutaki S Combi
- Yutaki S80
- Yutaki M

### Limitations

- 1 gateway per H-LINK system
- 1 Yutaki unit per ATW-MBS-02
- Not compatible with centralised remote controls, building air conditioning controls, other Hitachi BMS/Modbus gateways, or other units of the same model

## Hardware Specifications

| Item | Specifications |
|---|---|
| Power supply | 1~ 230 V ±10% 50 Hz |
| Consumption | 4.5W (maximum) |
| Outer dimensions | 106 × 90 × 58 mm (W × D × H) |
| Weight | 165 g |
| Ambient temperature | -10~60 °C |
| Humidity | 20~85% (without condensation) |

## Communication

### RS485

| Item | Specifications |
|---|---|
| Type | Modbus RTU |
| Connector | Serial Port RS485 (3 screw terminals) |
| Communication line | Shielded twisted pair cable, with third wire (common), with polarity |
| Communication system | Half-duplex, multipoint serial connection |
| Communication method | Non parity or odd/even parity selection. Data length: 8 bits – 1 stop bit |
| Baud rate | 19200/9600 Baud |
| Length | Max. 1200 m (EIA-485) |

### Ethernet

| Item | Specifications |
|---|---|
| Type | Modbus TCP |
| Connector | Ethernet (RJ45) |
| Communication line | Two twisted pair cable CAT5 or better (T-568A/T-568B) |
| Communication system | Full-duplex |
| Length | Max. 100 m (IEEE 802.3) |

### H-LINK

| Item | Specifications |
|---|---|
| Communication with | Hitachi Yutaki (S / S80 / S Combi / M) units |
| Communication line | Twisted pair shielded cable, non-polarity |
| Communication system | Half-duplex |
| Communication method | Asynchronous |
| Speed | 9600 Bauds |
| Length of wiring | 1000 m maximum (total length of H-LINK I/O bus) |
| Max gateways | 1 Gateway H-LINK SYSTEM |
| Max units | 1 YUTAKI per ATW-MBS-02 |

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
| SW1-1 | Configuration | Modbus end resistance |
| SW1-2 | Not used | Keep always ON |

## Register Addressing

The ATW-MBS-02 uses two numbering schemes in its documentation:

- **Register**: 1-based Modbus register number (as shown in the documentation)
- **Address**: 0-based Modbus address (Register - 1)

Example: Register 1001 = Address 1000

---

## Register Maps

The ATW-MBS-02 has two distinct register maps depending on the Yutaki hardware generation:

- **[Before Line-up 2016](#before-line-up-2016)**: Yutaki S, Yutaki S Combi (original models)
- **[Line-up 2016](#line-up-2016-series)**: Yutaki S, Yutaki S Combi, Yutaki S80, Yutaki M

---

# Before Line-up 2016

## General Parameters

### Control Registers (R/W)

| Register | Address | Description | Range | Type |
|---|---|---|---|---|
| 1001 | 1000 | Control Unit Run/Stop | 0: Stop, 1: Run | R/W |
| 1002 | 1001 | Control Unit Mode | 0: Cool (*2), 1: Heat | R/W |
| 1003 | 1002 | Control Circuit 1 Run/Stop | 0: Stop, 1: Run | R/W |
| 1004 | 1003 | Control Heat. OTC Circuit 1 | 0: No, 1: Points, 2: Gradient, 3: Fix | R/W |
| 1005 | 1004 | Control Cool. OTC Circuit 1 (*2) | 0: No, 1: Points, 2: Fix | R/W |
| 1006 | 1005 | Control Circuit 1: Thermostat Setting Temperature | 50~350 (5.0~35.0 °C) | R/W |
| 1007 | 1006 | Control Circuit 1: Thermostat Room Temperature (*5) | 0~1000 (0.0~100.0 °C) | R/W |
| 1008 | 1007 | Control Circuit 1: Water heating Fix Setting Temp | 0~80 °C (*3) | R/W |
| 1009 | 1008 | Control Circuit 1: Water cooling Fix Setting Temp (*2) | 0~80 °C (*3) | R/W |
| 1010 | 1009 | Control Circuit 2 Run/Stop | 0: Stop, 1: Run | R/W |
| 1011 | 1010 | Control Heat. OTC Circuit 2 | 0: No, 1: Points, 2: Gradient, 3: Fix | R/W |
| 1012 | 1011 | Control Cool. OTC Circuit 2 (*2) | 0: No, 1: Points, 2: Fix | R/W |
| 1013 | 1012 | Control Circuit 2: Thermostat Setting Temperature | 50~350 (5.0~35.0 °C) | R/W |
| 1014 | 1013 | Control Circuit 2: Thermostat Room Temperature (*5) | 0~1000 (0.0~100.0 °C) | R/W |
| 1015 | 1014 | Control Circuit 2: Water heating Fix Setting Temp | 0~80 °C (*3) | R/W |
| 1016 | 1015 | Control Circuit 2: Water cooling Fix Setting Temp (*2) | 0~80 °C (*3) | R/W |
| 1017 | 1016 | Control DHWT Run/Stop | 0: Stop, 1: Run | R/W |
| 1018 | 1017 | Control DHWT Setting Temperature | 0~80 °C (*3) | R/W |
| 1019 | 1018 | Control Swimming Pool Run/Stop | 0: Stop, 1: Run | R/W |
| 1020 | 1019 | Control Swimming Pool Setting Temperature | 0~80 °C (*3) | R/W |
| 1021 | 1020 | Control Anti Legionella Run (*6) | 0: Stop, 1: Run | R/W |
| 1022 | 1021 | Control AntiLegionella Setting Temperature | 0~80 °C (*3) | R/W |
| 1023 | 1022 | Control Block menu (*7) | 0: No, 1: Block | R/W |
| 1024 | 1023 | Control BMS Alarm (*8) | 0: No, 1: Alarm | R/W |
| 1025~1027 | 1024~1026 | (Reserved) | — | — |
| 1028 | 1027 | Space mode | 0: Comfort, 1: ECO | R/W |
| 1029 | 1028 | DHW Mode | 0: Standard, 1: High demand | R/W |
| 1030 | 1029 | Room Thermostat available (*4) | 0: No available, 1: Available | R/W |
| 1031 | 1030 | Control Eco offset | 1~10 | R/W |
| 1032~1050 | 1031~1049 | (Reserved) | — | — |

### Status Registers (R)

| Register | Address | Description | Range | Type |
|---|---|---|---|---|
| 1051 | 1050 | Status Unit Mode | 0: Cool (*2), 1: Heat | R |
| 1052 | 1051 | Status Circuit 1 Run/Stop | 0: Stop, 1: Run | R |
| 1053 | 1052 | Status Heat. OTC Circuit 1 | 0: No, 1: Points, 2: Gradient, 3: Fix | R |
| 1054 | 1053 | Status Cool. OTC Circuit 1 (*2) | 0: No, 1: Points, 2: Fix | R |
| 1055 | 1054 | Status Circuit 1: Thermostat Setting Temperature | 50~350 (5.0~35.0 °C) | R |
| 1056 | 1055 | Status Circuit 1: Thermostat Room Temperature | 0~1000 (0.0~100.0 °C) | R |
| 1057 | 1056 | Status Circuit 1: Water heating Fix Setting Temp | 0~80 °C (*3) | R |
| 1058 | 1057 | Status Circuit 1: Water cooling Fix Setting Temp (*2) | 0~80 °C (*3) | R |
| 1059 | 1058 | Status Circuit 2 Run/Stop | 0: Stop, 1: Run | R |
| 1060 | 1059 | Status Heating OTC Circuit 2 | 0: No, 1: Points, 2: Gradient, 3: Fix | R |
| 1061 | 1060 | Status Cooling OTC Circuit 2 (*2) | 0: No, 1: Points, 2: Fix | R |
| 1062 | 1061 | Status Circuit 2: Thermostat Setting Temperature | 50~350 (5.0~35.0 °C) | R |
| 1063 | 1062 | Status Circuit 2: Thermostat Room Temperature | 0~1000 (0.0~100.0 °C) | R |
| 1064 | 1063 | Status Circuit 2: Water heating Fix Setting Temp | 0~80 °C (*3) | R |
| 1065 | 1064 | Status Circuit 2: Water cooling Fix Setting Temp (*2) | 0~80 °C (*3) | R |
| 1066 | 1065 | Status DHWT Run/Stop | 0: Stop, 1: Run | R |
| 1067 | 1066 | Status DHWT Setting Temperature | 0~80 °C (*3) | R |
| 1068 | 1067 | Status Swim.Pool Run/Stop | 0: Stop, 1: Run | R |
| 1069 | 1068 | Status Swim. Pool Setting Temperature | 0~80 °C (*3) | R |
| 1070 | 1069 | Status AntiLeg. Run | 0: Stop, 1: Run | R |
| 1071 | 1070 | Status AntiLeg. Setting Temperature | 0~80 °C (*3) | R |
| 1072 | 1071 | Status block menu | 0: No, 1: Block | R |
| 1073 | 1072 | Status BMS Alarm | 0: No, 1: Alarm | R |
| 1074 | 1073 | LCD Central Mode | 0: Local, 1: Air, 2: Water, 3: Full | R |
| 1075 | 1074 | System Configuration | See [System Configuration Bits](#system-configuration-bits-before-2016) | R |
| 1076 | 1075 | DHWT Temperature | -80~100 °C (*1)(*3) | R |
| 1077 | 1076 | Swim temperature | -80~100 °C (*1)(*3) | R |
| 1078 | 1077 | Operation State | See [Operation State Values](#operation-state-values) | R |
| 1079 | 1078 | Outdoor Ambient T° | -80~100 °C (*1)(*3) | R |
| 1080 | 1079 | Water Inlet T° | -80~100 °C (*1)(*3) | R |
| 1081 | 1080 | Water outlet T° | -80~100 °C (*1)(*3) | R |
| 1082 | 1081 | Hardware version | — | R |
| 1083 | 1082 | Software version | — | R |
| 1084 | 1083 | H-LINK communication alarm state | See [H-LINK State Values](#h-link-communication-state-values) | R |
| 1085 | 1084 | LCD Software number | — | R |
| 1086 | 1085 | PCB1 Software number | — | R |
| 1087 | 1086 | Status Circuit 1: Wireless Setting Temperature (*9) | 50~350 (5.0~35.0 °C) | R |
| 1088 | 1087 | Status Circuit 2: Wireless Setting Temperature (*9) | 50~350 (5.0~35.0 °C) | R |
| 1089 | 1088 | Status Circuit 1: Wireless Room Temperature (*9) | 0~1000 (0.0~100.0 °C) | R |
| 1090 | 1089 | Status Circuit 2: Wireless Room Temperature (*9) | 0~1000 (0.0~100.0 °C) | R |
| 1091 | 1090 | Status Eco offset | 1~10 | R |

### System Configuration Bits (Before 2016)

Register 1075 (address 1074):

| Bit | Description |
|---|---|
| 0 | Circuit 1 Heating Available |
| 1 | Circuit 2 Heating Available |
| 2 | Circuit 1 Cooling Available (*2) |
| 3 | Circuit 2 Cooling Available (*2) |
| 4 | DHWT Available |
| 5 | SWP Available |
| 6 | Room thermostat available Circuit 1 |
| 7 | Room thermostat available Circuit 2 |

### Servicing Parameters (Before 2016)

| Register | Address | Description | Range | Type |
|---|---|---|---|---|
| 1200 | 1199 | Water outlet hp T° | 0~100 °C (Yutaki S & S Combi only) | R |
| 1201 | 1200 | Ta2: Outdoor Unit Ambient Average Temp. | -80~100 °C (*1)(*3) | R |
| 1202 | 1201 | Ta. Second Ambient Temperature | -80~100 °C (*1)(*3) | R |
| 1203 | 1202 | Ta3: Second ambient average temp. | -80~100 °C (*1)(*3) (Yutaki S Combi only) | R |
| 1204 | 1203 | O2: Water outlet Temp. 2 (Two2) | -80~100 °C (*1)(*3) | R |
| 1205 | 1204 | O3: Water outlet Temp. 3 (Two3) | -80~100 °C (*1)(*3) | R |
| 1206 | 1205 | Tg: Gas Temperature (THMg) | -80~100 °C (*1)(*3) | R |
| 1207 | 1206 | TI: Liquid Temperature (THMI) | -80~100 °C (*1)(*3) | R |
| 1208 | 1207 | Td: Discharge Gas temp | -80~100 °C (*1)(*3) | R |
| 1209 | 1208 | Te: Evaporation temp | -80~100 °C (*1)(*3) | R |
| 1210 | 1209 | EVI: Indoor Expansion valve opening | 0~100 % | R |
| 1211 | 1210 | EVO: Outdoor Expansion valve | 0~100 % | R |
| 1212 | 1211 | H4: Inverter Operation frequency | 0~115 Hz (*3) | R |
| 1213 | 1212 | DI: Cause of stoppage | — | R |
| 1214 | 1213 | P1: Compressor running current | 0~30 A (*3) | R |
| 1215 | 1214 | CD: Capacity data | — | R |
| 1216 | 1215 | MVP: Mixing valve position (%) | Only Circuit 2 | R |
| 1217 | 1216 | Defrosting | — | R |
| 1218 | 1217 | Unit model | 0: YUTAKI S, 1: YUTAKI S COMBI | R |
| 1219 | 1218 | Th: Water Temp. Setting (Ttwo) | -80~100 °C (*1)(*3) | R |
| 1221 | 1220 | Water flow level | 0~30 (0.0~3.0 m³/h) (Yutaki S Combi only) | R |
| 1222 | 1221 | Water pump speed (%) | (Yutaki S Combi only) | R |
| 1223 | 1222 | System status 2 | See [System Status 2 Bits (Before 2016)](#system-status-2-bits-before-2016) | R |
| 1224 | 1223 | Alarm number | 0: No Alarm, XXX: Alarm number | R |
| 1225 | 1224 | R134a Discharge Temperature | (Yutaki S80 only) | R |
| 1226 | 1225 | R134a Suction temperature | (Yutaki S80 only) | R |
| 1227 | 1226 | R134a Liquid temperature | (Yutaki S80 only) | R |
| 1228 | 1227 | R134a Evaporating temperature | (Yutaki S80 only) | R |
| 1229 | 1228 | R134a Discharge Pressure | (Yutaki S80 only) | R |
| 1230 | 1229 | R134a Suction pressure | (Yutaki S80 only) | R |
| 1231 | 1230 | R134a Compressor frequency | (Yutaki S80 only) | R |
| 1232 | 1231 | R134a Indoor Expansion valve opening | (Yutaki S80 only) | R |
| 1233 | 1232 | R134a Compressor current value | (Yutaki S80 only) | R |
| 1234 | 1233 | R134a Software number | (Yutaki S80 only) | R |
| 1235 | 1234 | R134a Retry Code | (Yutaki S80 only) | R |

### System Status 2 Bits (Before 2016)

Register 1223 (address 1222):

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
| 9 | Tarrif input enable |

---

# Line-up 2016 Series

## General Parameters

### Control Registers (R/W)

| Register | Address | Description | Range | Type |
|---|---|---|---|---|
| 1001 | 1000 | Control Unit Run/Stop | 0: Stop, 1: Run | R/W |
| 1002 | 1001 | Control Unit Mode | 0: Cool (*2), 1: Heat, 2: Auto | R/W |
| 1003 | 1002 | Control Circuit 1 Run/Stop | 0: Stop, 1: Run | R/W |
| 1004 | 1003 | Control Heat. OTC Circuit 1 | 0: No, 1: Points, 2: Gradient, 3: Fix | R/W |
| 1005 | 1004 | Control Cool. OTC Circuit 1 (*2) | 0: No, 1: Points, 2: Fix | R/W |
| 1006 | 1005 | Control Circuit 1: Water heating Fix Setting Temp | 0~80 °C (*3) | R/W |
| 1007 | 1006 | Control Circuit 1: Water cooling Fix Setting Temp (*2) | 0~80 °C (*3) | R/W |
| 1008 | 1007 | Control Circuit 1: Eco mode | 0: ECO, 1: Comfort | R/W |
| 1009 | 1008 | Control Circuit 1: Heat ECO Offset Temperature | 1~10 | R/W |
| 1010 | 1009 | Control Circuit 1: Cool ECO Offset Temperature (*2) | 1~10 | R/W |
| 1011 | 1010 | Control Circuit 1: Thermostat Available (*7) | 0: Not Available, 1: Available | R/W |
| 1012 | 1011 | Control Circuit 1: Thermostat Setting Temperature | 50~350 (5.0~35.0 °C) | R/W |
| 1013 | 1012 | Control Circuit 1: Thermostat Room Temperature (*8) | 0~1000 (0.0~100.0 °C) | R/W |
| 1014 | 1013 | Control Circuit 2 Run/Stop | 0: Stop, 1: Run | R/W |
| 1015 | 1014 | Control Heat. OTC Circuit 2 | 0: No, 1: Points, 2: Gradient, 3: Fix | R/W |
| 1016 | 1015 | Control Cool. OTC Circuit 2 (*2) | 0: No, 1: Points, 2: Fix | R/W |
| 1017 | 1016 | Control Circuit 2: Water heating Fix Setting Temp | 0~80 °C (*3) | R/W |
| 1018 | 1017 | Control Circuit 2: Water cooling Fix Setting Temp (*2) | 0~80 °C (*3) | R/W |
| 1019 | 1018 | Control Circuit 2: Eco mode | 0: ECO, 1: Comfort | R/W |
| 1020 | 1019 | Control Circuit 2: Heat ECO Offset Temperature | 1~10 | R/W |
| 1021 | 1020 | Control Circuit 2: Cool ECO Offset Temperature (*2) | 1~10 | R/W |
| 1022 | 1021 | Control Circuit 2: Thermostat Available (*7) | 0: Not Available, 1: Available | R/W |
| 1023 | 1022 | Control Circuit 2: Thermostat Setting Temperature | 50~350 (5.0~35.0 °C) | R/W |
| 1024 | 1023 | Control Circuit 2: Thermostat Room Temperature (*8) | 0~1000 (0.0~100.0 °C) | — |
| 1025 | 1024 | Control DHWT Run/Stop | 0: Stop, 1: Run | R/W |
| 1026 | 1025 | Control DHWT Setting Temperature | 0~80 °C (*3) | R/W |
| 1027 | 1026 | Control DHW Boost | 0: No request, 1: Request | R/W |
| 1028 | 1027 | Control DHW Demand Mode | 0: Standard, 1: High demand | R/W |
| 1029 | 1028 | Control Swimming Pool Run/Stop | 0: Stop, 1: Run | R/W |
| 1030 | 1029 | Control Swimming Pool Setting Temperature | 0~80 °C (*3) | R/W |
| 1031 | 1030 | Control Anti Legionella Run (*9) | 0: Stop, 1: Run | R/W |
| 1032 | 1031 | Control Anti Legionella Setting Temperature | 0~80 °C (*3) | R/W |
| 1033 | 1032 | Control Block menu (*6) | 0: No, 1: Block | R/W |
| 1034 | 1033 | Control BMS Alarm (*4) | 0: No Alarm, 1: Alarm | R/W |

### Status Registers (R)

| Register | Address | Description | Range | Type |
|---|---|---|---|---|
| 1051 | 1050 | Status Unit Run/Stop | 0: Stop, 1: Run | R |
| 1052 | 1051 | Status Unit Mode | 0: Cool (*2), 1: Heat | R |
| 1053 | 1052 | Status Circuit 1 Run/Stop | 0: Stop, 1: Run | R |
| 1054 | 1053 | Status Heat. OTC Circuit 1 | 0: No, 1: Points, 2: Gradient, 3: Fix | R |
| 1055 | 1054 | Status Cool. OTC Circuit 1 (*2) | 0: No, 1: Points, 2: Fix | R |
| 1056 | 1055 | Control Circuit 1: Water heating Fix Setting Temp | 0~80 °C (*3) | R |
| 1057 | 1056 | Control Circuit 1: Water cooling Fix Setting Temp (*2) | 0~80 °C (*3) | R |
| 1058 | 1057 | Status Circuit 1: Eco mode | 0: ECO, 1: Comfort | R |
| 1059 | 1058 | Status Circuit 1: Heat ECO Offset Temperature | 1~10 | R |
| 1060 | 1059 | Status Circuit 1: Cool ECO Offset Temperature (*2) | 1~10 | R |
| 1061 | 1060 | Status Circuit 1: Thermostat Setting Temperature | 50~350 (5.0~35.0 °C) | R |
| 1062 | 1061 | Status Circuit 1: Thermostat Room Temperature | 0~1000 (0.0~100.0 °C) | R |
| 1063 | 1062 | Status Circuit 1: Wireless Setting Temperature (*5) | 50~350 (5.0~35.0 °C) | R |
| 1064 | 1063 | Status Circuit 1: Wireless Room Temperature (*5) | 0~1000 (0.0~100.0 °C) | R |
| 1065 | 1064 | Status Circuit 2 Run/Stop | 0: Stop, 1: Run | R |
| 1066 | 1065 | Status Heat. OTC Circuit 2 | 0: No, 1: Points, 2: Gradient, 3: Fix | R |
| 1067 | 1066 | Status Cool. OTC Circuit 2 (*2) | 0: No, 1: Points, 2: Fix | R |
| 1068 | 1067 | Status Circuit 2: Water heating Fix Setting Temp | 0~80 °C (*3) | R |
| 1069 | 1068 | Status Circuit 2: Water cooling Fix Setting Temp (*2) | 0~80 °C (*3) | R |
| 1070 | 1069 | Status Circuit 2: Eco mode | 0: ECO, 1: Comfort | R |
| 1071 | 1070 | Status Circuit 2: Heat ECO Offset Temperature | 1~10 | R |
| 1072 | 1071 | Status Circuit 2: Cool ECO Offset Temperature (*2) | 1~10 | R |
| 1073 | 1072 | Status Circuit 2: Thermostat Setting Temperature | 50~350 (5.0~35.0 °C) | R |
| 1074 | 1073 | Status Circuit 2: Thermostat Room Temperature | 0~1000 (0.0~100.0 °C) | R |
| 1075 | 1074 | Status Circuit 2: Wireless Setting Temperature (*5) | 50~350 (5.0~35.0 °C) | R |
| 1076 | 1075 | Status Circuit 2: Wireless Room Temperature (*5) | 0~1000 (0.0~100.0 °C) | R |
| 1077 | 1076 | Status DHWT Run/Stop | 0: Stop, 1: Run | R |
| 1078 | 1077 | Status DHWT Setting Temperature | 0~80 °C (*3) | R |
| 1079 | 1078 | Control DHW Boost | 0: Disable, 1: Enable | R |
| 1080 | 1079 | Status DHW Demand Mode | 0: Standard, 1: High demand | R |
| 1081 | 1080 | Status DHW Temperature | -80~100 °C (*1) | R |
| 1082 | 1081 | Status Swimming Pool Run/Stop | 0: Stop, 1: Run | R |
| 1083 | 1082 | Status Swimming Pool Setting Temperature | 0~80 °C (*3) | R |
| 1084 | 1083 | Status Swimming Pool Temperature | -80~100 °C (*1) | R |
| 1085 | 1084 | Status Anti Legionella Run | 0: Stop, 1: Run | R |
| 1086 | 1085 | Status Anti Legionella Setting Temperature | 0~80 °C (*3) | R |
| 1087 | 1086 | Status Block menu (*6) | 0: No, 1: Block | R |
| 1088 | 1087 | Status BMS Alarm | 0: No, 1: Alarm | R |
| 1089 | 1088 | Central Mode | 0: Local, 1: Air, 2: Water, 3: Full | R |
| 1090 | 1089 | System Configuration | See [System Configuration Bits (2016)](#system-configuration-bits-2016) | R |
| 1091 | 1090 | Operation State | See [Operation State Values](#operation-state-values) | R |
| 1092 | 1091 | Outdoor ambient temperature | -80~100 °C (*1) | R |
| 1093 | 1092 | Water Inlet unit temperature | -80~100 °C (*1) | R |
| 1094 | 1093 | Water outlet unit temperature | -80~100 °C (*1) | R |
| 1095 | 1094 | H-LINK communication state | See [H-LINK State Values](#h-link-communication-state-values) | R |
| 1096 | 1095 | Software PCB | — | R |
| 1097 | 1096 | Software LCD | — | R |
| 1098 | 1097 | Unit Capacity | 0~255 kWh | R |
| 1099 | 1098 | Unit Power consumption | 0~255 kWh | R |

### System Configuration Bits (2016)

Register 1090 (address 1089):

| Bit | Description |
|---|---|
| 0 | Circuit 1 Heating |
| 1 | Circuit 2 Heating |
| 2 | Circuit 1 Cooling (*2) |
| 3 | Circuit 2 Cooling (*2) |
| 4 | DHWT |
| 5 | SWP |
| 6 | Room thermostat Circuit 1 |
| 7 | Room thermostat Circuit 2 |
| 8 | Wireless setting Circuit 1 |
| 9 | Wireless setting Circuit 2 |
| 10 | Wireless room temperature Circuit 1 |
| 11 | Wireless room temperature Circuit 2 |

## Servicing Parameters (2016)

| Register | Address | Description | Range | Type |
|---|---|---|---|---|
| 1201 | 1200 | Water outlet hp T° | 0~100 °C | R |
| 1202 | 1201 | Ta2: Outdoor Unit Ambient Average Temp. | -80~100 °C (*1) | R |
| 1203 | 1202 | Ta. Second Ambient Temperature | -80~100 °C (*1) | R |
| 1204 | 1203 | Ta3: Second ambient average temp. | -80~100 °C (*1) | R |
| 1205 | 1204 | O2: Water outlet Temp. 2 (Two2) | -80~100 °C (*1) | R |
| 1206 | 1205 | O3: Water outlet Temp. 3 (Two3) | -80~100 °C (*1) | R |
| 1207 | 1206 | Tg: Gas Temperature (THMg) | -80~100 °C (*1) | R |
| 1208 | 1207 | TI: Liquid Temperature (THMI) | -80~100 °C (*1) | R |
| 1209 | 1208 | Td: Discharge Gas temp | -80~100 °C (*1) | R |
| 1210 | 1209 | Te: Evaporation temp | -80~100 °C (*1) | R |
| 1211 | 1210 | EVI: Indoor Expansion valve opening | 0~100 % | R |
| 1212 | 1211 | EVO: Outdoor Expansion valve | 0~100 % | R |
| 1213 | 1212 | H4: Inverter Operation frequency | 0~115 Hz (*3) | R |
| 1214 | 1213 | DI: Cause of stoppage | — | R |
| 1215 | 1214 | P1: Compressor running current | 0~30 A (*3) | R |
| 1216 | 1215 | CD: Capacity data | — | R |
| 1217 | 1216 | MVP: Mixing valve position | Only Circuit 2 | R |
| 1218 | 1217 | Defrosting | — | R |
| 1219 | 1218 | Unit model | 0: YUTAKI S, 1: YUTAKI S COMBI, 2: S80, 3: M | R |
| 1220 | 1219 | Th: Water Temp. Setting (Ttwo) | -80~100 °C (*1) | R |
| 1221 | 1220 | Water flow level | 0~30 (0.0~3.0 m³/h) | R |
| 1222 | 1221 | Water pump speed | 0~100 % | R |
| 1223 | 1222 | System status 2 | See [System Status 2 Bits (2016)](#system-status-2-bits-2016) | R |
| 1224 | 1223 | Alarm number | 0: No Alarm, XXX: Alarm number | R |

### R134a Secondary Compressor (Yutaki S80 only)

| Register | Address | Description | Range | Type |
|---|---|---|---|---|
| 1225 | 1224 | R134a Discharge Temperature | -80~100 °C (*1) | R |
| 1226 | 1225 | R134a Suction temperature | -80~100 °C (*1) | R |
| 1227 | 1226 | R134a Discharge Pressure | 0~510 (0.00~5.10 MPa) | R |
| 1228 | 1227 | R134a Suction pressure | 0~255 (0.00~2.55 MPa) | R |
| 1229 | 1228 | R134a Compressor frequency | 0~115 Hz (*3) | R |
| 1230 | 1229 | R134a Indoor Expansion valve 2 opening | 0~100 % | R |
| 1231 | 1230 | R134a Compressor current value | 0~300 (0.00~30.0 A) | R |
| 1232 | 1231 | R134a Retry Code | — | R |

### System Status 2 Bits (2016)

Register 1223 (address 1222):

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
| 9 | Smart function input enable |

---

## Common Reference Values

### Operation State Values

Register 1091 (2016) / Register 1078 (before 2016), address 1090 / 1077:

| Value | Description |
|---|---|
| 0 | OFF |
| 1 | Cool Demand–OFF (*2) |
| 2 | Cool Thermo-OFF (*2) |
| 3 | Cool Thermo-ON (*2) |
| 4 | Heat Demand-OFF |
| 5 | Heat Thermo-OFF |
| 6 | Heat Thermo-ON |
| 7 | DHW-OFF |
| 8 | DHW-ON |
| 9 | SWP-OFF |
| 10 | SWP-ON |
| 11 | Alarm |

### H-LINK Communication State Values

| Value | Description |
|---|---|
| 0 | No alarm |
| 1 | No communication with RCS or YUTAKI unit during more than 180 seconds |
| 2 | Data initialization |

---

## Notes

- **(*1)** These numbers are expressed as a signed 16-bit value using 2-complement format for negative values.
- **(*2)** Only for Heating and Cooling units.
- **(*3)** This value is limited by the machine according to their rank.
- **(*4)** This parameter informs that the modbus net is in alarm.
- **(*5)** These parameters show thermostat setting and room temperature, which may be different from those in the unit when using central control (Thermostat and Room sensors via Modbus).
- **(*6)** Access to menu in unit control is blocked.
- **(*7)** Enable this parameter when using Modbus thermostat.
- **(*8)** This parameter can only be used if no have installed HITACHI thermostat, only when using Modbus thermostat. Unless the central bit is enabled, so the HITACHI thermostat is used only for setting temperature.
- **(*9)** This parameter can only be used if the function is enabled on the LCD.
