"""Interactive dashboard over the DuckDB warehouse.

Run:
    streamlit run app/dashboard.py
"""

from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"

st.set_page_config(page_title="Malaysia Inflation & Fuel Dashboard", layout="wide")


@st.cache_data
def query(sql: str) -> pd.DataFrame:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.execute(sql).df()


if not DB_PATH.exists():
    st.error("Warehouse not found. Run `python src/ingest.py` then `python src/build_warehouse.py` first.")
    st.stop()

st.title("🇲🇾 Malaysia Inflation & Fuel Prices")
st.caption(
    "Official DOSM open data (data.gov.my) → DuckDB star schema → this dashboard. "
    "All figures are year-over-year CPI changes unless stated."
)

# ---- KPI row ----------------------------------------------------------------
latest = query(
    """
    SELECT division_code, division_name, yoy_pct, month_date
    FROM marts.cpi_yoy_national
    WHERE month_date = (SELECT max(month_date) FROM marts.cpi_yoy_national)
    """
)
latest_month = pd.to_datetime(latest["month_date"].iloc[0])
fuel_now = query("SELECT * FROM marts.fact_fuel_price ORDER BY date_key DESC LIMIT 1")


def kpi(df: pd.DataFrame, code: str) -> str:
    row = df[df["division_code"] == code]
    return f"{row['yoy_pct'].iloc[0]:+.1f}%" if not row.empty else "n/a"


c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Headline CPI ({latest_month:%b %Y})", kpi(latest, "overall"))
c2.metric("Food & Beverages", kpi(latest, "01"))
c3.metric("Transport", kpi(latest, "07"))
c4.metric("RON97 (latest week)", f"RM {fuel_now['ron97_rm'].iloc[0]:.2f}/L")

# ---- Division explorer ------------------------------------------------------
st.subheader("Inflation by division")
divisions = query(
    "SELECT DISTINCT division_code, division_name FROM marts.cpi_yoy_national ORDER BY division_code"
)
chosen = st.multiselect(
    "Divisions",
    options=divisions["division_name"].tolist(),
    default=["Overall CPI", "Food & Beverages", "Transport"],
)
years = st.slider("From year", 2012, int(latest_month.year), 2018)

if chosen:
    series = query(
        f"""
        SELECT month_date, division_name, yoy_pct
        FROM marts.cpi_yoy_national
        WHERE division_name IN ({','.join("'" + c.replace("'", "''") + "'" for c in chosen)})
          AND month_date >= DATE '{years}-01-01' AND yoy_pct IS NOT NULL
        ORDER BY month_date
        """
    )
    chart = (
        alt.Chart(series)
        .mark_line()
        .encode(
            x=alt.X("month_date:T", title=None),
            y=alt.Y("yoy_pct:Q", title="YoY %"),
            color=alt.Color("division_name:N", title=None),
            tooltip=["month_date:T", "division_name", "yoy_pct"],
        )
        .properties(height=340)
    )
    st.altair_chart(chart, width="stretch")

# ---- State comparison ---------------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("States, latest month")
    states = query(
        """
        SELECT state_name, yoy_pct FROM marts.cpi_yoy_state
        WHERE month_date = (SELECT max(month_date) FROM marts.cpi_yoy_state)
          AND yoy_pct IS NOT NULL
        ORDER BY yoy_pct DESC
        """
    )
    st.altair_chart(
        alt.Chart(states)
        .mark_bar(color="#0f62fe")
        .encode(
            x=alt.X("yoy_pct:Q", title="YoY %"),
            y=alt.Y("state_name:N", sort="-x", title=None),
            tooltip=["state_name", "yoy_pct"],
        )
        .properties(height=380),
        width="stretch",
    )

with right:
    st.subheader("Pump prices (RM/litre)")
    fuel = query(
        "SELECT date_key, ron95_rm AS RON95, ron97_rm AS RON97, diesel_rm AS Diesel FROM marts.fact_fuel_price ORDER BY date_key"
    )
    fuel_long = fuel.melt("date_key", var_name="fuel", value_name="rm")
    st.altair_chart(
        alt.Chart(fuel_long.dropna())
        .mark_line()
        .encode(
            x=alt.X("date_key:T", title=None),
            y=alt.Y("rm:Q", title="RM/litre", scale=alt.Scale(zero=False)),
            color=alt.Color("fuel:N", title=None),
            tooltip=["date_key:T", "fuel", "rm"],
        )
        .properties(height=380),
        width="stretch",
    )

st.caption(
    "Source: Department of Statistics Malaysia via api.data.gov.my · "
    "github.com/azizghaus14/malaysia-open-data-pipeline"
)
