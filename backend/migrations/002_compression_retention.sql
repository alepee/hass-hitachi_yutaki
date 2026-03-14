-- 002_compression_retention.sql
-- Compression, retention policies, and continuous aggregates

-- === COMPRESSION ===

-- Compress metrics older than 7 days (~90-95% storage reduction)
ALTER TABLE metrics SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instance_hash',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('metrics', compress_after => INTERVAL '7 days');

-- Compress snapshots older than 7 days
ALTER TABLE register_snapshots SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instance_hash, profile',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('register_snapshots', compress_after => INTERVAL '7 days');

-- === RETENTION ===

-- Drop fine metrics after 30 days (daily_stats preserves long-term view)
SELECT add_retention_policy('metrics', drop_after => INTERVAL '30 days');

-- Keep snapshots 90 days (test fixture value, then expendable)
SELECT add_retention_policy('register_snapshots', drop_after => INTERVAL '90 days');

-- daily_stats: NO retention policy (kept indefinitely, small volume)

-- === CONTINUOUS AGGREGATE: auto-downsample metrics → daily view ===

CREATE MATERIALIZED VIEW metrics_daily_agg
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time)      AS bucket,
    instance_hash,
    MIN(outdoor_temp)               AS outdoor_temp_min,
    MAX(outdoor_temp)               AS outdoor_temp_max,
    AVG(outdoor_temp)               AS outdoor_temp_avg,
    AVG(cop_instant)                AS cop_avg,
    MIN(cop_instant)                AS cop_min,
    MAX(cop_instant)                AS cop_max,
    AVG(thermal_power)              AS thermal_power_avg,
    AVG(electrical_power)           AS electrical_power_avg,
    COUNT(*) FILTER (WHERE compressor_on = TRUE)  AS compressor_on_samples,
    COUNT(*) FILTER (WHERE is_defrosting = TRUE)  AS defrost_samples,
    COUNT(*)                        AS total_samples
FROM metrics
GROUP BY bucket, instance_hash
WITH NO DATA;

-- Refresh daily, re-materialize last 3 days (handles late-arriving data)
SELECT add_continuous_aggregate_policy('metrics_daily_agg',
    start_offset    => INTERVAL '3 days',
    end_offset      => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day'
);
