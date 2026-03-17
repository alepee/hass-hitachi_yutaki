-- 004_world_model_fields.sql
-- Add setpoint, control state, and flow fields for world model training

ALTER TABLE metrics
    ADD COLUMN circuit1_target_temp   REAL,
    ADD COLUMN circuit2_target_temp   REAL,
    ADD COLUMN dhw_target_temp        REAL,
    ADD COLUMN water_target_temp      REAL,
    ADD COLUMN water_flow             REAL,
    ADD COLUMN circuit1_otc_method_heating TEXT,
    ADD COLUMN circuit1_otc_method_cooling TEXT,
    ADD COLUMN circuit1_eco_mode      BOOLEAN,
    ADD COLUMN circuit2_eco_mode      BOOLEAN,
    ADD COLUMN circuit1_power         BOOLEAN,
    ADD COLUMN circuit2_power         BOOLEAN,
    ADD COLUMN dhw_power              BOOLEAN;

-- Grant INSERT on new columns to worker role
-- (column-level grants not needed; table-level INSERT covers all columns)
