-- ---------------------------------------------------------------------------
-- MARTS LAYER, part 2: analysis-ready marts
-- Window functions compute year-over-year inflation from the index levels.
-- ---------------------------------------------------------------------------

-- National YoY inflation per division per month.
CREATE OR REPLACE TABLE marts.cpi_yoy_national AS
SELECT
    f.date_key                       AS month_date,
    f.division_code,
    d.division_name,
    f.cpi_index,
    round(
        100.0 * (f.cpi_index / lag(f.cpi_index, 12)
            OVER (PARTITION BY f.division_code ORDER BY f.date_key) - 1), 2
    )                                AS yoy_pct
FROM marts.fact_cpi_national f
JOIN marts.dim_division d USING (division_code)
ORDER BY f.date_key, f.division_code;

-- Overall YoY inflation per state per month.
CREATE OR REPLACE TABLE marts.cpi_yoy_state AS
SELECT
    f.date_key                       AS month_date,
    s.state_name,
    f.cpi_index,
    round(
        100.0 * (f.cpi_index / lag(f.cpi_index, 12)
            OVER (PARTITION BY s.state_name ORDER BY f.date_key) - 1), 2
    )                                AS yoy_pct
FROM marts.fact_cpi_state f
JOIN marts.dim_state s USING (state_key)
WHERE f.division_code = 'overall'
ORDER BY f.date_key, s.state_name;

-- Monthly average pump prices (fuel is weekly; CPI is monthly).
CREATE OR REPLACE TABLE marts.fuel_monthly AS
SELECT
    date_trunc('month', date_key)   AS month_date,
    round(avg(ron95_rm), 3)         AS ron95_rm,
    round(avg(ron97_rm), 3)         AS ron97_rm,
    round(avg(diesel_rm), 3)        AS diesel_rm
FROM marts.fact_fuel_price
GROUP BY 1
ORDER BY 1;

-- Transport CPI inflation vs pump-price movement (do administered fuel
-- prices insulate transport inflation?).
CREATE OR REPLACE TABLE marts.transport_vs_fuel AS
SELECT
    t.month_date,
    t.yoy_pct                        AS transport_cpi_yoy_pct,
    fm.ron95_rm,
    fm.ron97_rm,
    round(
        100.0 * (fm.ron97_rm / lag(fm.ron97_rm, 12) OVER (ORDER BY t.month_date) - 1), 2
    )                                AS ron97_yoy_pct
FROM marts.cpi_yoy_national t
JOIN marts.fuel_monthly fm USING (month_date)
WHERE t.division_code = '07'
ORDER BY t.month_date;
