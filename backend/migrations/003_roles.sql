-- 003_roles.sql
-- Database roles and permissions
-- IMPORTANT: Change passwords before running!

-- === WRITER ROLE (Cloudflare Worker — INSERT only) ===
CREATE ROLE worker_write WITH LOGIN PASSWORD 'CHANGE_ME_worker';

GRANT CONNECT ON DATABASE tsdb TO worker_write;
GRANT USAGE ON SCHEMA public TO worker_write;

-- Worker can INSERT into all data tables
GRANT INSERT ON installations, metrics, daily_stats, register_snapshots TO worker_write;
-- Worker needs UPDATE for installations upsert (ON CONFLICT DO UPDATE)
GRANT UPDATE ON installations TO worker_write;

-- Future tables get same privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT INSERT ON TABLES TO worker_write;

-- === READ-ONLY ROLE (Grafana + psql/Claude Code) ===
CREATE ROLE grafana_read WITH LOGIN PASSWORD 'CHANGE_ME_grafana';

GRANT CONNECT ON DATABASE tsdb TO grafana_read;
GRANT USAGE ON SCHEMA public TO grafana_read;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_read;

-- Include continuous aggregates (they are materialized views)
GRANT SELECT ON metrics_daily_agg TO grafana_read;

-- Future tables get SELECT
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO grafana_read;
