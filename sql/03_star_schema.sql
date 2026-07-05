-- ---------------------------------------------------------------------------
-- MARTS LAYER, part 1: dimensional model (star schema)
--
--   dim_date ----< fact_cpi_national >---- dim_division
--   dim_date ----< fact_cpi_state    >---- dim_division, dim_state
--   dim_date ----< fact_fuel_price
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS marts;

-- Date dimension covering every date that appears in any fact.
CREATE OR REPLACE TABLE marts.dim_date AS
WITH all_dates AS (
    SELECT month_date AS d FROM clean.cpi_national
    UNION
    SELECT month_date FROM clean.cpi_state
    UNION
    SELECT price_date FROM clean.fuel_price
)
SELECT
    d                              AS date_key,
    EXTRACT(year FROM d)           AS year,
    EXTRACT(month FROM d)          AS month,
    strftime(d, '%b %Y')           AS month_label,
    'Q' || EXTRACT(quarter FROM d) AS quarter
FROM all_dates
ORDER BY d;

-- COICOP 2018 divisions as published by DOSM (post-2024 CPI rebase).
CREATE OR REPLACE TABLE marts.dim_division AS
SELECT * FROM (VALUES
    ('overall', 'Overall CPI'),
    ('01', 'Food & Beverages'),
    ('02', 'Alcoholic Beverages & Tobacco'),
    ('03', 'Clothing & Footwear'),
    ('04', 'Housing, Water, Electricity, Gas & Other Fuels'),
    ('05', 'Furnishings & Household Maintenance'),
    ('06', 'Health'),
    ('07', 'Transport'),
    ('08', 'Information & Communication'),
    ('09', 'Recreation, Sport & Culture'),
    ('10', 'Education'),
    ('11', 'Restaurant & Accommodation Services'),
    ('12', 'Insurance & Financial Services'),
    ('13', 'Personal Care & Miscellaneous')
) AS t(division_code, division_name);

CREATE OR REPLACE TABLE marts.dim_state AS
SELECT
    row_number() OVER (ORDER BY state_name) AS state_key,
    state_name
FROM (SELECT DISTINCT state_name FROM clean.cpi_state);

CREATE OR REPLACE TABLE marts.fact_cpi_national AS
SELECT
    c.month_date    AS date_key,
    c.division_code,
    c.cpi_index
FROM clean.cpi_national c
JOIN marts.dim_division d USING (division_code);

CREATE OR REPLACE TABLE marts.fact_cpi_state AS
SELECT
    c.month_date    AS date_key,
    s.state_key,
    c.division_code,
    c.cpi_index
FROM clean.cpi_state c
JOIN marts.dim_state s USING (state_name)
JOIN marts.dim_division d USING (division_code);

CREATE OR REPLACE TABLE marts.fact_fuel_price AS
SELECT
    price_date AS date_key,
    ron95_rm,
    ron97_rm,
    diesel_rm
FROM clean.fuel_price;
