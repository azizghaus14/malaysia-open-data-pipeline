-- ---------------------------------------------------------------------------
-- CLEAN LAYER
-- Typed, deduplicated, validated tables. One row per natural key.
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS clean;

-- Weekly retail fuel prices. The source mixes 'level' rows (actual prices)
-- with 'change_weekly' rows (week-over-week deltas); we keep levels only.
CREATE OR REPLACE TABLE clean.fuel_price AS
SELECT
    CAST(date AS DATE)      AS price_date,
    CAST(ron95 AS DOUBLE)   AS ron95_rm,
    CAST(ron97 AS DOUBLE)   AS ron97_rm,
    CAST(diesel AS DOUBLE)  AS diesel_rm
FROM raw.fuelprice
WHERE COALESCE(series_type, 'level') = 'level'
  AND date IS NOT NULL
QUALIFY row_number() OVER (PARTITION BY date ORDER BY date) = 1
ORDER BY price_date;

-- Monthly national CPI by COICOP division ('overall' plus divisions 01-13).
CREATE OR REPLACE TABLE clean.cpi_national AS
SELECT
    CAST(date AS DATE)        AS month_date,
    CAST(division AS VARCHAR) AS division_code,
    CAST("index" AS DOUBLE)   AS cpi_index
FROM raw.cpi_headline
WHERE date IS NOT NULL
  AND "index" IS NOT NULL
  AND CAST("index" AS DOUBLE) BETWEEN 10 AND 500   -- guard against corrupt values
QUALIFY row_number() OVER (PARTITION BY date, division ORDER BY date) = 1
ORDER BY month_date, division_code;

-- Monthly CPI by state and COICOP division.
CREATE OR REPLACE TABLE clean.cpi_state AS
SELECT
    CAST(date AS DATE)        AS month_date,
    trim(CAST(state AS VARCHAR))  AS state_name,
    CAST(division AS VARCHAR) AS division_code,
    CAST("index" AS DOUBLE)   AS cpi_index
FROM raw.cpi_state
WHERE date IS NOT NULL
  AND state IS NOT NULL
  AND "index" IS NOT NULL
  AND CAST("index" AS DOUBLE) BETWEEN 10 AND 500
QUALIFY row_number() OVER (PARTITION BY date, state, division ORDER BY date) = 1
ORDER BY month_date, state_name, division_code;
