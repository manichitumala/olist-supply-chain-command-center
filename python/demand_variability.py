"""
Phase 6 - Demand variability.

For every product category, aggregates weekly demand and computes mean,
standard deviation, coefficient of variation (CV) and per-week Z-scores.
Flags weeks with |Z| > 2 as anomalies (spike or drop).
"""

import pandas as pd

from config import CHARTS_DIR, EXPORTS_DIR, REPORTS_DIR, ROOT
from db import get_engine

RAW_SQL = (ROOT / "sql" / "kpis" / "05_demand_raw.sql").read_text(encoding="utf-8")

MIN_WEEKS = 8  # categories with too few active weeks can't get a meaningful CV


def classify_cv(cv: float) -> str:
    if pd.isna(cv):
        return "Insufficient data"
    if cv < 0.5:
        return "Stable"
    if cv <= 1.0:
        return "Variable"
    return "Highly Variable"


def main():
    engine = get_engine()
    weekly = pd.read_sql(RAW_SQL, engine, parse_dates=["week_start"])

    weekly["z_score"] = weekly.groupby("category_en")["n_items_sold"].transform(
        lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) > 0 else 0.0
    )
    weekly["anomaly"] = weekly["z_score"].apply(
        lambda z: "Spike" if z > 2 else ("Drop" if z < -2 else "Normal")
    )

    summary = weekly.groupby("category_en").agg(
        n_weeks_active=("n_items_sold", "count"),
        mean_weekly_demand=("n_items_sold", "mean"),
        std_weekly_demand=("n_items_sold", "std"),
        total_items=("n_items_sold", "sum"),
        total_revenue=("revenue", "sum"),
    ).reset_index()

    summary["coefficient_of_variation"] = (
        summary["std_weekly_demand"] / summary["mean_weekly_demand"]
    ).round(3)
    summary["demand_class"] = summary["coefficient_of_variation"].apply(classify_cv)
    summary.loc[summary["n_weeks_active"] < MIN_WEEKS, "demand_class"] = "Insufficient data"

    anomaly_counts = (
        weekly[weekly["anomaly"] != "Normal"]
        .groupby("category_en")
        .size()
        .rename("anomaly_weeks")
    )
    summary = summary.merge(anomaly_counts, on="category_en", how="left")
    summary["anomaly_weeks"] = summary["anomaly_weeks"].fillna(0).astype(int)
    summary["anomaly_frequency"] = (summary["anomaly_weeks"] / summary["n_weeks_active"]).round(3)

    summary = summary.sort_values("coefficient_of_variation", ascending=False)

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    summary.round(2).to_csv(EXPORTS_DIR / "demand_variability_by_category.csv", index=False)
    weekly.to_csv(EXPORTS_DIR / "demand_weekly_detail.csv", index=False)

    anomalies = weekly[weekly["anomaly"] != "Normal"].sort_values("z_score", ascending=False)
    anomalies.to_csv(EXPORTS_DIR / "demand_anomalies.csv", index=False)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    class_counts = summary["demand_class"].value_counts()
    lines = [
        "# Demand Variability Analysis",
        "",
        f"Weekly demand computed for {summary.shape[0]} product categories "
        f"(categories need >= {MIN_WEEKS} active weeks to receive a CV classification).",
        "",
        "## Demand class distribution",
        "",
        class_counts.to_markdown(),
        "",
        "## 10 most volatile categories (highest CV)",
        "",
        summary.head(10)[[
            "category_en", "mean_weekly_demand", "coefficient_of_variation",
            "demand_class", "anomaly_frequency",
        ]].to_markdown(index=False),
        "",
        f"## Anomalous weeks flagged (|Z| > 2): {len(anomalies)}",
        "",
        anomalies.head(15)[[
            "category_en", "week_start", "n_items_sold", "z_score", "anomaly",
        ]].to_markdown(index=False),
    ]
    (REPORTS_DIR / "demand_variability_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(class_counts)
    print(f"{len(anomalies)} anomalous category-weeks flagged.")


if __name__ == "__main__":
    main()
