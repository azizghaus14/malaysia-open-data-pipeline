"""Data-quality suite for the warehouse, run with pytest.

These are the checks a production pipeline would run after every load:
completeness, uniqueness, validity, referential integrity, and continuity.
Run `python src/build_warehouse.py` first.
"""

from pathlib import Path

import duckdb
import pytest

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"


@pytest.fixture(scope="session")
def con():
    if not DB_PATH.exists():
        pytest.skip("warehouse not built -- run `python src/build_warehouse.py` first")
    connection = duckdb.connect(str(DB_PATH), read_only=True)
    yield connection
    connection.close()


def one(con, sql: str):
    return con.execute(sql).fetchone()[0]


# --- completeness -----------------------------------------------------------

def test_tables_are_populated(con):
    expectations = {
        "clean.fuel_price": 400,        # weekly since 2017
        "clean.cpi_national": 5_000,    # monthly since 1980, 14 divisions
        "clean.cpi_state": 30_000,      # monthly since 2010, 16 states
        "marts.fact_cpi_state": 30_000,
        "marts.cpi_yoy_national": 5_000,
    }
    for table, minimum in expectations.items():
        assert one(con, f"SELECT count(*) FROM {table}") >= minimum, table


def test_all_16_states_present(con):
    assert one(con, "SELECT count(*) FROM marts.dim_state") == 16


def test_all_divisions_mapped(con):
    unmapped = one(
        con,
        """
        SELECT count(*) FROM clean.cpi_national c
        LEFT JOIN marts.dim_division d USING (division_code)
        WHERE d.division_code IS NULL
        """,
    )
    assert unmapped == 0


# --- uniqueness -------------------------------------------------------------

@pytest.mark.parametrize(
    ("table", "key"),
    [
        ("clean.fuel_price", "price_date"),
        ("clean.cpi_national", "month_date, division_code"),
        ("clean.cpi_state", "month_date, state_name, division_code"),
    ],
)
def test_natural_keys_are_unique(con, table, key):
    dupes = one(
        con,
        f"SELECT count(*) FROM (SELECT {key} FROM {table} GROUP BY {key} HAVING count(*) > 1)",
    )
    assert dupes == 0


# --- validity ---------------------------------------------------------------

def test_cpi_index_within_plausible_range(con):
    bad = one(
        con,
        "SELECT count(*) FROM marts.fact_cpi_national WHERE cpi_index NOT BETWEEN 10 AND 500",
    )
    assert bad == 0


def test_fuel_prices_within_plausible_range(con):
    """Upper bound is 8, not 6: after the 2024-2025 subsidy rationalisation,
    market-priced diesel reached RM 6.72/litre (Apr 2026)."""
    bad = one(
        con,
        """
        SELECT count(*) FROM marts.fact_fuel_price
        WHERE ron97_rm NOT BETWEEN 1 AND 8 OR diesel_rm NOT BETWEEN 1 AND 8
        """,
    )
    assert bad == 0


def test_yoy_inflation_is_sane(con):
    """Malaysia has not seen |YoY CPI| anywhere near 40% in this period."""
    bad = one(
        con,
        "SELECT count(*) FROM marts.cpi_yoy_national WHERE abs(yoy_pct) > 40",
    )
    assert bad == 0


# --- referential integrity --------------------------------------------------

def test_fact_cpi_state_joins_to_dimensions(con):
    orphans = one(
        con,
        """
        SELECT count(*) FROM marts.fact_cpi_state f
        LEFT JOIN marts.dim_state s USING (state_key)
        LEFT JOIN marts.dim_division d USING (division_code)
        LEFT JOIN marts.dim_date dd ON f.date_key = dd.date_key
        WHERE s.state_key IS NULL OR d.division_code IS NULL OR dd.date_key IS NULL
        """,
    )
    assert orphans == 0


# --- continuity / freshness -------------------------------------------------

def test_national_overall_series_has_no_month_gaps(con):
    gaps = one(
        con,
        """
        WITH series AS (
            SELECT date_key,
                   lag(date_key) OVER (ORDER BY date_key) AS prev
            FROM marts.fact_cpi_national
            WHERE division_code = 'overall'
        )
        SELECT count(*) FROM series
        WHERE prev IS NOT NULL AND date_diff('month', prev, date_key) != 1
        """,
    )
    assert gaps == 0


def test_data_is_reasonably_fresh(con):
    latest = one(con, "SELECT max(date_key) FROM marts.fact_cpi_national")
    assert str(latest) >= "2026-01-01"
