-- 006_geolocation.sql
-- Add anonymized geolocation (rounded to 1°) and climate zone

ALTER TABLE installations
    ADD COLUMN latitude      REAL,
    ADD COLUMN longitude     REAL,
    ADD COLUMN climate_zone  TEXT;
