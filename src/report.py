"""Generate charts and an auto-filled findings report from the warehouse.

Outputs:
    reports/figures/*.png
    reports/summary.md

Usage:
    python src/report.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "warehouse.duckdb"
FIG_DIR = REPO_ROOT / "reports" / "figures"

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "figure.figsize": (9, 4.5),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "font.size": 9,
    }
)


def save(fig, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG_DIR / name)
    plt.close(fig)
    print(f"[report] wrote reports/figures/{name}")


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # -- 1. Headline inflation since 2015 ------------------------------------
    headline = con.execute(
        """
        SELECT month_date, yoy_pct FROM marts.cpi_yoy_national
        WHERE division_code = 'overall' AND month_date >= DATE '2015-01-01'
          AND yoy_pct IS NOT NULL
        ORDER BY month_date
        """
    ).df()
    latest_month = headline["month_date"].iloc[-1]
    latest_yoy = headline["yoy_pct"].iloc[-1]

    fig, ax = plt.subplots()
    ax.plot(headline["month_date"], headline["yoy_pct"], color="#0f62fe", lw=1.6)
    ax.axhline(0, color="grey", lw=0.8)
    ax.annotate(
        f"{latest_yoy:+.1f}%",
        (latest_month, latest_yoy),
        xytext=(8, 6),
        textcoords="offset points",
        fontweight="bold",
        color="#0f62fe",
    )
    ax.set_title("Malaysia headline CPI inflation (YoY %)")
    ax.set_ylabel("YoY %")
    save(fig, "headline_inflation.png")

    # -- 2. Division breakdown, latest month ---------------------------------
    divisions = con.execute(
        """
        SELECT division_name, yoy_pct FROM marts.cpi_yoy_national
        WHERE month_date = (SELECT max(month_date) FROM marts.cpi_yoy_national)
          AND division_code != 'overall' AND yoy_pct IS NOT NULL
        ORDER BY yoy_pct
        """
    ).df()

    fig, ax = plt.subplots(figsize=(9, 5))
    colors = ["#da1e28" if v > latest_yoy else "#0f62fe" for v in divisions["yoy_pct"]]
    ax.barh(divisions["division_name"], divisions["yoy_pct"], color=colors)
    ax.axvline(latest_yoy, color="grey", ls="--", lw=1, label=f"headline {latest_yoy:+.1f}%")
    ax.set_title(f"CPI inflation by division, {latest_month:%b %Y} (YoY %)")
    ax.legend()
    save(fig, "division_yoy_latest.png")

    # -- 3. State comparison, latest month ------------------------------------
    states = con.execute(
        """
        SELECT state_name, yoy_pct FROM marts.cpi_yoy_state
        WHERE month_date = (SELECT max(month_date) FROM marts.cpi_yoy_state)
          AND yoy_pct IS NOT NULL
        ORDER BY yoy_pct
        """
    ).df()

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(states["state_name"], states["yoy_pct"], color="#0f62fe")
    ax.set_title(f"Overall CPI inflation by state, {latest_month:%b %Y} (YoY %)")
    save(fig, "state_yoy_latest.png")

    # -- 4. Pump prices --------------------------------------------------------
    fuel = con.execute(
        "SELECT date_key, ron95_rm, ron97_rm, diesel_rm FROM marts.fact_fuel_price ORDER BY date_key"
    ).df()

    fig, ax = plt.subplots()
    ax.plot(fuel["date_key"], fuel["ron95_rm"], label="RON95", color="#0f62fe", lw=1.4)
    ax.plot(fuel["date_key"], fuel["ron97_rm"], label="RON97", color="#da1e28", lw=1.4)
    ax.plot(fuel["date_key"], fuel["diesel_rm"], label="Diesel (Peninsular)", color="#198038", lw=1.4)
    ax.set_title("Weekly retail fuel prices (RM/litre)")
    ax.legend()
    save(fig, "fuel_prices.png")

    # -- 5. Transport CPI vs market-priced fuel --------------------------------
    tvf = con.execute(
        """
        SELECT month_date, transport_cpi_yoy_pct, ron97_yoy_pct
        FROM marts.transport_vs_fuel
        WHERE transport_cpi_yoy_pct IS NOT NULL AND ron97_yoy_pct IS NOT NULL
        ORDER BY month_date
        """
    ).df()
    corr = tvf["transport_cpi_yoy_pct"].corr(tvf["ron97_yoy_pct"])

    fig, ax = plt.subplots()
    ax.plot(tvf["month_date"], tvf["transport_cpi_yoy_pct"], label="Transport CPI YoY %", color="#0f62fe", lw=1.4)
    ax.plot(tvf["month_date"], tvf["ron97_yoy_pct"], label="RON97 price YoY %", color="#da1e28", lw=1.4, alpha=0.8)
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_title(f"Transport CPI vs RON97 pump price (YoY %), r = {corr:.2f}")
    ax.legend()
    save(fig, "transport_vs_fuel.png")

    # -- summary.md -------------------------------------------------------------
    top = divisions.iloc[-1]
    bottom = divisions.iloc[0]
    hi_state = states.iloc[-1]
    lo_state = states.iloc[0]
    latest_fuel = fuel.dropna(subset=["ron97_rm"]).iloc[-1]

    summary = f"""# Findings summary

_Auto-generated by `src/report.py` on {date.today()} from `data/warehouse.duckdb`._

## Latest reading: {latest_month:%B %Y}

| Indicator | Value |
|---|---|
| Headline CPI inflation (YoY) | **{latest_yoy:+.1f}%** |
| Hottest division | **{top['division_name']}** ({top['yoy_pct']:+.1f}%) |
| Coolest division | **{bottom['division_name']}** ({bottom['yoy_pct']:+.1f}%) |
| Highest-inflation state | **{hi_state['state_name']}** ({hi_state['yoy_pct']:+.1f}%) |
| Lowest-inflation state | **{lo_state['state_name']}** ({lo_state['yoy_pct']:+.1f}%) |
| RON97 pump price ({latest_fuel['date_key']:%d %b %Y}) | RM {latest_fuel['ron97_rm']:.2f}/litre |

## Transport CPI vs pump prices

Correlation between transport-CPI YoY and RON97-price YoY (2018-present):
**r = {corr:.2f}**. Market-priced RON97 moves with global oil, while the
administered RON95 price cap means headline transport inflation is largely
insulated from oil shocks -- visible as RON97 swinging far more than the
transport CPI line.

## Charts

![Headline inflation](figures/headline_inflation.png)
![Division breakdown](figures/division_yoy_latest.png)
![State comparison](figures/state_yoy_latest.png)
![Fuel prices](figures/fuel_prices.png)
![Transport vs fuel](figures/transport_vs_fuel.png)
"""
    out = REPO_ROOT / "reports" / "summary.md"
    out.write_text(summary)
    print(f"[report] wrote {out.relative_to(REPO_ROOT)}")
    con.close()


if __name__ == "__main__":
    main()
