-- ---------------------------------------------------------------------------
-- RAW LAYER
-- Load the ingested API snapshots exactly as delivered (no transformation).
-- DuckDB reads the gzipped JSON directly.
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS raw;

CREATE OR REPLACE TABLE raw.fuelprice AS
SELECT * FROM read_json_auto('data/raw/fuelprice.json.gz');

CREATE OR REPLACE TABLE raw.cpi_headline AS
SELECT * FROM read_json_auto('data/raw/cpi_headline.json.gz');

CREATE OR REPLACE TABLE raw.cpi_state AS
SELECT * FROM read_json_auto('data/raw/cpi_state.json.gz');
