"""Export the warehouse marts as flat CSVs for BI tools (Power BI, Tableau).

Power BI Desktop is Windows-only, and the browser service cannot upload a local
file without a paid capacity, so these CSVs are committed and served over HTTPS
from GitHub. The Power BI report connects to the raw URLs below, which means the
report refreshes straight from this repository and anyone can reproduce it.

Usage:
    python powerbi/export_for_powerbi.py
"""

from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "warehouse.duckdb"
OUT_DIR = Path(__file__).resolve().parent

EXPORTS = {
    "cpi_national.csv": """
        SELECT month_date AS "Month", division_code AS "DivisionCode",
               division_name AS "Division", cpi_index AS "CPI Index", yoy_pct AS "YoY %"
        FROM marts.cpi_yoy_national WHERE yoy_pct IS NOT NULL ORDER BY month_date, division_code
    """,
    "cpi_state.csv": """
        SELECT month_date AS "Month", state_name AS "State",
               cpi_index AS "CPI Index", yoy_pct AS "YoY %"
        FROM marts.cpi_yoy_state WHERE yoy_pct IS NOT NULL ORDER BY month_date, state_name
    """,
    "fuel_prices.csv": """
        SELECT date_key AS "Date", ron95_rm AS "RON95", ron97_rm AS "RON97", diesel_rm AS "Diesel"
        FROM marts.fact_fuel_price ORDER BY date_key
    """,
    "transport_vs_fuel.csv": """
        SELECT month_date AS "Month", transport_cpi_yoy_pct AS "Transport CPI YoY %",
               ron97_rm AS "RON97 RM", ron97_yoy_pct AS "RON97 YoY %"
        FROM marts.transport_vs_fuel
        WHERE transport_cpi_yoy_pct IS NOT NULL AND ron97_yoy_pct IS NOT NULL ORDER BY month_date
    """,
}


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        for name, sql in EXPORTS.items():
            path = OUT_DIR / name
            con.execute(f"COPY ({sql.strip()}) TO '{path}' (HEADER, DELIMITER ',')")
            rows = con.execute(f"SELECT count(*) FROM ({sql.strip()})").fetchone()[0]
            print(f"[powerbi] {name:<24} {rows:>6,} rows")
    finally:
        con.close()


if __name__ == "__main__":
    main()
