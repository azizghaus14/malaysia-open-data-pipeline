"""Build the DuckDB warehouse from the raw layer.

Executes the SQL files in sql/ in order:

    01_load_raw.sql     raw.*    -- gzipped JSON snapshots loaded as-is
    02_clean.sql        clean.*  -- typed, deduplicated, validated tables
    03_star_schema.sql  marts.*  -- dimensional model (dims + facts)
    04_marts.sql        marts.*  -- analysis-ready marts (YoY inflation, fuel trends)

The result is a single portable file: data/warehouse.duckdb.

Usage:
    python src/build_warehouse.py
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "warehouse.duckdb"
SQL_DIR = REPO_ROOT / "sql"


def main() -> None:
    # SQL files reference data/raw/ relative to the repo root.
    os.chdir(REPO_ROOT)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = duckdb.connect(str(DB_PATH))
    try:
        for sql_file in sorted(SQL_DIR.glob("*.sql")):
            con.execute(sql_file.read_text())
            print(f"[warehouse] executed {sql_file.name}")

        tables = con.execute(
            """
            SELECT table_schema, table_name,
                   (SELECT count(*) FROM duckdb_columns() c
                     WHERE c.schema_name = t.table_schema
                       AND c.table_name = t.table_name) AS n_cols
            FROM information_schema.tables t
            WHERE table_schema IN ('raw', 'clean', 'marts')
            ORDER BY table_schema, table_name
            """
        ).fetchall()
        print(f"\n[warehouse] built {DB_PATH.relative_to(REPO_ROOT)}:")
        for schema, name, n_cols in tables:
            n_rows = con.execute(f'SELECT count(*) FROM "{schema}"."{name}"').fetchone()[0]
            print(f"  {schema}.{name:<24} {n_rows:>8,} rows  {n_cols} cols")
    finally:
        con.close()


if __name__ == "__main__":
    main()
