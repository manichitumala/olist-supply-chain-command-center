"""
Writes dashboard/data.js for the static HTML dashboard (dashboard/index.html).
Kept so the existing dashboard keeps working until the Streamlit app replaces it.
"""

import json

import duckdb
import pandas as pd

from src.config import ROOT, Settings
from src.db import query_file

DASHBOARD_DIR = ROOT / "dashboard"


def records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def run(con: duckdb.DuckDBPyConnection, settings: Settings) -> int:
    data = {}
    headline = query_file(con, "kpis/01_executive_kpis.sql", 0)
    data["executive"] = {
        "headline": records(headline)[0],
        "monthly_trend": records(query_file(con, "kpis/01_executive_kpis.sql", 1)),
    }
    data["fulfilment"] = {
        "stage_avg": records(query_file(con, "kpis/02_fulfilment_kpis.sql", 0))[0],
        "monthly_stage_trend": records(query_file(con, "kpis/02_fulfilment_kpis.sql", 1)),
        "stage_by_otd_status": records(query_file(con, "kpis/02_fulfilment_kpis.sql", 2)),
    }
    scatter = query_file(con, "kpis/03_logistics_kpis.sql", 2)
    data["logistics"] = {
        "distance_band_summary": records(query_file(con, "kpis/03_logistics_kpis.sql", 0)),
        "state_performance": records(query_file(con, "kpis/03_logistics_kpis.sql", 1)),
        "scatter_sample": records(scatter.sample(n=min(2500, len(scatter)), random_state=42)[
            ["distance_km", "lead_time_days", "freight_value", "otd_status"]].round(2)),
    }

    ex = settings.exports_dir
    sellers = pd.read_csv(ex / "seller_scorecard.csv")
    scored = sellers[sellers["seller_score"].notna()].round(2)
    data["sellers"] = {
        "tier_counts": sellers["performance_tier"].value_counts().to_dict(),
        "top_10": records(scored.head(10)),
        "bottom_10": records(scored.tail(10)),
    }
    demand = pd.read_csv(ex / "demand_variability_by_category.csv")
    risk = pd.read_csv(ex / "supply_chain_risk_index.csv")
    data["demand_risk"] = {
        "demand_class_counts": demand["demand_class"].value_counts().to_dict(),
        "most_volatile_categories": records(
            demand[demand["demand_class"] != "Insufficient data"].head(10).round(3)),
        "risk_tier_counts": risk["risk_tier"].value_counts().to_dict(),
        "top_risk_categories": records(risk.head(10).round(1)),
    }
    data["root_cause"] = {
        name: records(pd.read_csv(ex / f"root_cause_{name}.csv"))
        for name in ["worst_sellers", "transport_delay", "multi_seller_complexity"]
    }

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    path = DASHBOARD_DIR / "data.js"
    path.write_text("const DASHBOARD_DATA = " + json.dumps(data) + ";\n", encoding="utf-8")
    return path.stat().st_size


def main(settings: Settings | None = None):
    from src.config import get_settings
    from src.db import connect

    settings = settings or get_settings()
    with connect(settings) as con:
        print(f"  wrote dashboard/data.js ({run(con, settings):,} bytes)")


if __name__ == "__main__":
    main()
