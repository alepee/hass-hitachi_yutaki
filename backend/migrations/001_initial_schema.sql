-- 001_initial_schema.sql
-- Anonymous telemetry schema for Hitachi Yutaki integration
-- Target: TigerData (TimescaleDB)

-- Anonymous installation identity (upserted daily)
CREATE TABLE installations (
    instance_hash            TEXT PRIMARY KEY,
    profile                  TEXT NOT NULL,
    gateway_type             TEXT NOT NULL,
    ha_version               TEXT,
    integration_version      TEXT,
    power_supply             TEXT,
    has_dhw                  BOOLEAN,
    has_pool                 BOOLEAN,
    has_cooling              BOOLEAN,
    max_circuits             SMALLINT,
    has_secondary_compressor BOOLEAN,
    first_seen               TIMESTAMPTZ DEFAULT NOW(),
    last_seen                TIMESTAMPTZ DEFAULT NOW()
);

-- Fine metrics (Full level, batch every 5min)
CREATE TABLE metrics (
    time                     TIMESTAMPTZ NOT NULL,
    instance_hash            TEXT NOT NULL,
    outdoor_temp             REAL,
    water_inlet_temp         REAL,
    water_outlet_temp        REAL,
    dhw_temp                 REAL,
    compressor_on            BOOLEAN,
    compressor_frequency     REAL,
    compressor_current       REAL,
    thermal_power            REAL,
    electrical_power         REAL,
    cop_instant              REAL,
    cop_quality              TEXT,
    unit_mode                TEXT,
    is_defrosting            BOOLEAN,
    dhw_active               BOOLEAN,
    circuit1_water_temp      REAL,
    circuit2_water_temp      REAL
);

SELECT create_hypertable('metrics', by_range('time'),
    chunk_time_interval => INTERVAL '1 day'
);
CREATE INDEX idx_metrics_instance ON metrics (instance_hash, time DESC);

-- Daily aggregates (sent at day boundary)
CREATE TABLE daily_stats (
    date                     DATE NOT NULL,
    instance_hash            TEXT NOT NULL,
    outdoor_temp_min         REAL,
    outdoor_temp_max         REAL,
    outdoor_temp_avg         REAL,
    cop_avg                  REAL,
    cop_min                  REAL,
    cop_max                  REAL,
    cop_quality_best         TEXT,
    compressor_starts        INTEGER,
    compressor_hours         REAL,
    defrost_count            INTEGER,
    defrost_total_minutes    REAL,
    thermal_energy_kwh       REAL,
    electrical_energy_kwh    REAL,
    heating_hours            REAL,
    cooling_hours            REAL,
    dhw_hours                REAL,
    PRIMARY KEY (date, instance_hash)
);

-- Modbus register snapshots (Full level, 24h after opt-in)
CREATE TABLE register_snapshots (
    time                     TIMESTAMPTZ NOT NULL,
    instance_hash            TEXT NOT NULL,
    profile                  TEXT NOT NULL,
    gateway_type             TEXT NOT NULL,
    registers                JSONB NOT NULL
);

SELECT create_hypertable('register_snapshots', by_range('time'),
    chunk_time_interval => INTERVAL '7 days'
);
CREATE INDEX idx_snapshots_instance ON register_snapshots (instance_hash, time DESC);
CREATE INDEX idx_snapshots_profile ON register_snapshots (profile, time DESC);
