-- 007_jsonb_metrics.sql
-- Add JSONB data column for flexible metric storage.
-- Existing typed columns remain for backward compatibility with current data.

ALTER TABLE metrics ADD COLUMN IF NOT EXISTS data JSONB;
