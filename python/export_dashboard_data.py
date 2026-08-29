"""
Aggregates gold-layer + analysis outputs into dashboard/data.js so the
dashboard is a single static HTML file with no server/backend needed.
Run this last, after every other analysis script.
"""

import json

import pandas as pd

from config import DASHBOARD_DIR, EXPORTS_DIR, ROOT
from db import get_engine

KPI_DIR = ROOT / "sql" / "kpis"


def statements(sql_text):
    return [s.strip() for s in sql_text.split(";") if s.strip()]


def main():
    engine = get_engine()
    data = {}

    with engine.connect() as conn:
        exec_stmts = statements((KPI_DIR / "01_executive_kpis.sql").read_text(encoding="utf-8"))
        headline = pd.read_sql(exec_stmts[0], conn).iloc[0].to_dict()
        monthly = pd.read_sql(exec_stmts[1], conn)
        data["executive"] = {"headline": headline, "monthly_trend": monthly.to_dict(orient="records")}

        fulfil_stmts = statements((KPI_DIR / "02_fulfilment_kpis.sql").read_text(encoding="utf-8"))
        stage_avg = pd.read_sql(fulfil_stmts[0], conn).iloc[0].to_dict()
        stage_monthly = pd.read_sql(fulfil_stmts[1], conn)
        stage_by_otd = pd.read_sql(fulfil_stmts[2], conn)
        data["fulfilment"] = {
            "stage_avg": stage_avg,
            "monthly_stage_trend": stage_monthly.to_dict(orient="records"),
            "stage_by_otd_status": stage_by_otd.to_dict(orient="records"),
        }

        logi_stmts = statements((KPI_DIR / "03_logistics_kpis.sql").read_text(encoding="utf-8"))
        distance_band = pd.read_sql(logi_stmts[0], conn)
        state_perf = pd.read_sql(logi_stmts[1], conn)
        scatter = pd.read_sql(logi_stmts[2], conn)
        scatter_sample = scatter.sample(n=min(2500, len(scatter)), random_state=42)
        data["logistics"] = {
            "distance_band_summary": distance_band.to_dict(orient="records"),
            "state_performance": state_perf.to_dict(orient="records"),
            "scatter_sample": scatter_sample[
                ["distance_km", "lead_time_days", "freight_value", "otd_status"]
            ].to_dict(orient="records"),
        }

    seller_scores = pd.read_csv(EXPORTS_DIR / "seller_scorecard.csv")
    tier_counts = seller_scores["performance_tier"].value_counts().to_dict()
    data["sellers"] = {
        "tier_counts": tier_counts,
        "top_10": seller_scores.head(10).to_dict(orient="records"),
        "bottom_10": seller_scores.tail(10).to_dict(orient="records"),
    }

    demand = pd.read_csv(EXPORTS_DIR / "demand_variability_by_category.csv")
    demand_class_counts = demand["demand_class"].value_counts().to_dict()
    risk = pd.read_csv(EXPORTS_DIR / "supply_chain_risk_index.csv")
    risk_tier_counts = risk["risk_tier"].value_counts().to_dict()
    data["demand_risk"] = {
        "demand_class_counts": demand_class_counts,
        "most_volatile_categories": demand.sort_values(
            "coefficient_of_variation", ascending=False
        ).head(10).to_dict(orient="records"),
        "risk_tier_counts": risk_tier_counts,
        "top_risk_categories": risk.head(10).to_dict(orient="records"),
    }

    root_cause = {
        "worst_sellers": pd.read_csv(EXPORTS_DIR / "root_cause_worst_sellers.csv").to_dict(orient="records"),
        "transport_delay": pd.read_csv(EXPORTS_DIR / "root_cause_transport_delay.csv").to_dict(orient="records"),
        "multi_seller_complexity": pd.read_csv(EXPORTS_DIR / "root_cause_multi_seller_complexity.csv").to_dict(orient="records"),
    }
    data["root_cause"] = root_cause

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    js = "const DASHBOARD_DATA = " + json.dumps(data, indent=None, default=str) + ";\n"
    (DASHBOARD_DIR / "data.js").write_text(js, encoding="utf-8")
    print(f"Wrote dashboard/data.js ({(DASHBOARD_DIR / 'data.js').stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
