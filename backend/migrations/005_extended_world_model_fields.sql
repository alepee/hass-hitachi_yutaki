-- 005_extended_world_model_fields.sql
-- Complete thermodynamic, compressor, and system state fields for world model

ALTER TABLE metrics
    -- Circuit 2 OTC methods
    ADD COLUMN circuit2_otc_method_heating  TEXT,
    ADD COLUMN circuit2_otc_method_cooling  TEXT,
    -- OTC parameters (all circuits)
    ADD COLUMN circuit1_max_flow_temp_heating REAL,
    ADD COLUMN circuit1_max_flow_temp_cooling REAL,
    ADD COLUMN circuit1_heat_eco_offset     REAL,
    ADD COLUMN circuit1_cool_eco_offset     REAL,
    ADD COLUMN circuit2_max_flow_temp_heating REAL,
    ADD COLUMN circuit2_max_flow_temp_cooling REAL,
    ADD COLUMN circuit2_heat_eco_offset     REAL,
    ADD COLUMN circuit2_cool_eco_offset     REAL,
    -- Primary compressor thermodynamics
    ADD COLUMN compressor_tg_gas_temp       REAL,
    ADD COLUMN compressor_ti_liquid_temp    REAL,
    ADD COLUMN compressor_td_discharge_temp REAL,
    ADD COLUMN compressor_te_evaporator_temp REAL,
    ADD COLUMN compressor_evi_valve_opening REAL,
    ADD COLUMN compressor_evo_valve_opening REAL,
    -- Secondary compressor (S80 cascade R134a)
    ADD COLUMN secondary_compressor_frequency         REAL,
    ADD COLUMN secondary_compressor_discharge_temp     REAL,
    ADD COLUMN secondary_compressor_suction_temp       REAL,
    ADD COLUMN secondary_compressor_discharge_pressure REAL,
    ADD COLUMN secondary_compressor_suction_pressure   REAL,
    ADD COLUMN secondary_compressor_valve_opening      REAL,
    -- System state
    ADD COLUMN unit_power                  BOOLEAN,
    ADD COLUMN pump_speed                  REAL,
    ADD COLUMN operation_state_code        SMALLINT,
    ADD COLUMN alarm_code                  SMALLINT,
    ADD COLUMN system_status               INTEGER,
    -- DHW modes
    ADD COLUMN dhw_boost                   BOOLEAN,
    ADD COLUMN dhw_high_demand             BOOLEAN,
    -- Additional temperatures
    ADD COLUMN water_outlet_2_temp         REAL,
    ADD COLUMN water_outlet_3_temp         REAL,
    ADD COLUMN pool_current_temp           REAL,
    ADD COLUMN pool_target_temp            REAL;
