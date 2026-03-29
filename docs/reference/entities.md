# Entity Reference

Complete list of entities created by the integration, organized by device. The
integration automatically detects your heat pump model and creates devices based
on your system configuration.

For patterns and conventions used to build these entities, see
[Entity Patterns](entity-patterns.md).

## Gateway Device

| Entity | Type | Description | Category |
|--------|------|-------------|----------|
| connectivity | binary_sensor | Indicates if the gateway is connected and responding | diagnostic |
| system_state | sensor | Gateway synchronization state with the heat pump | diagnostic |
| telemetry_status | sensor | Current telemetry consent level (off/on) with send tracking attributes | diagnostic |

## Heat Pump Control Unit Device

### Controls

| Entity | Type | Description | Values |
|--------|------|-------------|--------|
| power | switch | Main power switch for the heat pump unit | on/off |
| operation_mode | select | Operating mode of the heat pump (modes depend on configuration) | heat only, or heat/cool/auto |

### Temperatures

| Entity | Type | Description | Unit |
|--------|------|-------------|------|
| outdoor_temp | sensor | Outdoor ambient temperature measurement | °C |
| water_inlet_temp | sensor | Water temperature at the heat pump inlet | °C |
| water_outlet_temp | sensor | Water temperature at the heat pump outlet | °C |
| water_outlet_2_temp | sensor | Water outlet 2 temperature (Two2, conditional) | °C |
| water_outlet_3_temp | sensor | Water outlet 3 temperature (Two3, conditional) | °C |
| water_target_temp | sensor | Corrected target water temperature | °C |

### System Status

| Entity | Type | Description | Category |
|--------|------|-------------|----------|
| operation_state | sensor | Current operation state with detailed description | diagnostic |
| alarm | sensor | Current alarm status | diagnostic |
| defrost | binary_sensor | Unit is currently in defrost mode | diagnostic |
| compressor | binary_sensor | Compressor is running | diagnostic |
| boiler | binary_sensor | Backup boiler is active (if supported) | diagnostic |
| dhw_heater | binary_sensor | DHW electric heater is active (if DHW configured) | diagnostic |
| solar | binary_sensor | Solar system is active (disabled by default) | diagnostic |
| space_heater | binary_sensor | Space heating electric heater is active (disabled by default) | diagnostic |
| smart_function | binary_sensor | Smart grid function is active (disabled by default) | diagnostic |

### Hydraulic

| Entity | Type | Description | Unit | Category |
|--------|------|-------------|------|----------|
| water_flow | sensor | Current water flow rate through the system | m³/h | diagnostic |
| pump_speed | sensor | Current speed of the water circulation pump | % | diagnostic |
| pump1 | binary_sensor | Water pump 1 is running (disabled by default) | - | diagnostic |
| pump2 | binary_sensor | Water pump 2 is running (disabled by default) | - | diagnostic |
| pump3 | binary_sensor | Water pump 3 is running (disabled by default) | - | diagnostic |

### Electrical Energy

| Entity | Type | Description | Unit | Category |
|--------|------|-------------|------|----------|
| power_consumption | sensor | Total electrical energy consumed by the unit | kWh | diagnostic |

### Thermal Energy

| Entity | Type | Description | Unit | Category |
|--------|------|-------------|------|----------|
| thermal_power_heating | sensor | Real-time thermal heating power output | kW | diagnostic |
| thermal_power_cooling | sensor | Real-time thermal cooling power output (cooling circuits only) | kW | diagnostic |
| thermal_energy_heating_daily | sensor | Daily thermal heating energy (resets at midnight) | kWh | diagnostic |
| thermal_energy_heating_total | sensor | Total cumulative thermal heating energy | kWh | diagnostic |
| thermal_energy_cooling_daily | sensor | Daily thermal cooling energy (cooling circuits only) | kWh | diagnostic |
| thermal_energy_cooling_total | sensor | Total cumulative thermal cooling energy (cooling circuits only) | kWh | diagnostic |

### Performance (COP)

| Entity | Type | Description | Category |
|--------|------|-------------|----------|
| cop_heating | sensor | Space heating COP | diagnostic |
| cop_cooling | sensor | Space cooling COP (cooling circuits only) | diagnostic |
| cop_dhw | sensor | Domestic hot water COP (if DHW configured) | diagnostic |
| cop_pool | sensor | Pool heating COP (if pool configured) | diagnostic |

Each COP sensor exposes additional attributes: `quality`, `measurements`, and
`time_span_minutes`.

## Primary Compressor Device

| Entity | Type | Description | Unit | Category |
|--------|------|-------------|------|----------|
| compressor_running | binary_sensor | Compressor is running | - | diagnostic |
| compressor_frequency | sensor | Operating frequency | Hz | diagnostic |
| compressor_current | sensor | Electrical current draw | A | diagnostic |
| compressor_tg_gas_temp | sensor | Gas temperature | °C | diagnostic |
| compressor_ti_liquid_temp | sensor | Liquid temperature | °C | diagnostic |
| compressor_td_discharge_temp | sensor | Discharge temperature | °C | diagnostic |
| compressor_te_evaporator_temp | sensor | Evaporator temperature | °C | diagnostic |
| compressor_evi_indoor_expansion_valve_opening | sensor | Indoor expansion valve opening | % | diagnostic |
| compressor_evo_outdoor_expansion_valve_opening | sensor | Outdoor expansion valve opening | % | diagnostic |
| compressor_cycle_time | sensor | Average time between compressor starts | min | diagnostic |
| compressor_runtime | sensor | Compressor runtime | min | diagnostic |
| compressor_resttime | sensor | Compressor rest time | min | diagnostic |

## Secondary Compressor Device (S80 Model Only)

| Entity | Type | Description | Unit | Category |
|--------|------|-------------|------|----------|
| secondary_compressor_running | binary_sensor | Secondary compressor is running | - | diagnostic |
| secondary_compressor_frequency | sensor | Operating frequency | Hz | diagnostic |
| secondary_compressor_current | sensor | Electrical current draw | A | diagnostic |
| secondary_compressor_discharge_temp | sensor | Discharge temperature | °C | diagnostic |
| secondary_compressor_suction_temp | sensor | Suction temperature | °C | diagnostic |
| secondary_compressor_discharge_pressure | sensor | Discharge pressure | bar | diagnostic |
| secondary_compressor_suction_pressure | sensor | Suction pressure | bar | diagnostic |
| secondary_compressor_cycle_time | sensor | Average time between compressor starts | min | diagnostic |
| secondary_compressor_runtime | sensor | Compressor runtime | min | diagnostic |
| secondary_compressor_resttime | sensor | Compressor rest time | min | diagnostic |

## Circuit Device (up to 2 circuits)

### Climate and Controls

| Entity | Type | Description | Values |
|--------|------|-------------|--------|
| climate | climate | Main climate control entity | off/heat/cool/auto or off/heat_cool |
| eco_mode | switch | Enable ECO mode (reduced temperatures) | on/off |
| thermostat | switch | Enable Modbus thermostat function (if available) | on/off |

### Configuration (disabled by default)

| Entity | Type | Description | Values/Unit | Category |
|--------|------|-------------|-------------|----------|
| otc_calculation_method_heating | select | Heating water temperature calculation method | disabled/points/gradient/fix | config |
| otc_calculation_method_cooling | select | Cooling water temperature calculation method | disabled/points/fix | config |
| max_flow_temp_heating_otc | number | Maximum heating water temperature for OTC | °C (0–80) | config |
| max_flow_temp_cooling_otc | number | Maximum cooling water temperature for OTC | °C (0–80) | config |
| heat_eco_offset | number | Temperature offset in ECO mode for heating | °C (1–10) | config |
| cool_eco_offset | number | Temperature offset in ECO mode for cooling | °C (1–10) | config |

### Service

| Service | Description | Fields |
|---------|-------------|--------|
| `hitachi_yutaki.set_room_temperature` | Set the room temperature for a circuit | `temperature` (0–50°C, step 0.1) |

## Domestic Hot Water Device (if configured)

| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| dhw | water_heater | Main DHW control entity | off/standard/high demand, 30–60°C |
| boost | switch | Temporarily boost DHW production | on/off |
| antilegionella | button | Manually start a high temperature anti-legionella cycle | - |
| antilegionella_temp | number | Target temperature for anti-legionella treatment (disabled by default) | °C (60–80) |
| antilegionella_cycle | binary_sensor | Anti-legionella cycle is currently running | on/off |

## Swimming Pool Device (if configured)

| Entity | Type | Description | Values/Unit |
|--------|------|-------------|-------------|
| power | switch | Power switch for swimming pool heating | on/off |
| pool_target_temp | number | Target temperature for swimming pool water | °C (0–80) |
| pool_current_temp | sensor | Current pool water temperature | °C |
