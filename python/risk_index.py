"""
Phase 9 - Supply Chain Risk Index.

Combines three independently-normalised risk components per product
category into one 0-100 Supply Chain Risk score:
    40% Demand Risk    (CV + anomaly frequency)
    35% Delivery Risk  (late rate + avg delay + transit variability)
    25% Seller Risk    (revenue-weighted 100 - seller_score)

Run after seller_scorecard.py and demand_variability.py, since it reuses
their outputs.
"""

import pandas as pd

from config import EXPORTS_DIR, REPORTS_DIR, ROOT
from db import get_engine

CATEGORY_DELIVERY_SQL = (ROOT / "sql" / "kpis" / "06_category_delivery_raw.sql").read_text(encoding="utf-8")

WEIGHTS = {"demand_risk": 0.40, "delivery_risk": 0.35, "seller_risk": 0.25}


def min_max_normalize(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(50.0, index=series.index)
    return (series - lo) / (hi - lo) * 100.0


def classify_risk(score: float) -> str:
    if score <= 30:
        return "LOW RISK"
    if score <= 60:
        return "MEDIUM RISK"
    return "HIGH RISK"


def main():
    engine = get_engine()

    demand = pd.read_csv(EXPORTS_DIR / "demand_variability_by_category.csv")
    delivery = pd.read_sql(CATEGORY_DELIVERY_SQL, engine)

    df = demand.merge(delivery, on="category_en", how="inner")

    # --- Demand Risk: CV + anomaly frequency, each normalised then averaged
    df["cv_norm"] = min_max_normalize(df["coefficient_of_variation"].fillna(0))
    df["anomaly_norm"] = min_max_normalize(df["anomaly_frequency"].fillna(0))
    df["demand_risk"] = (df["cv_norm"] + df["anomaly_norm"]) / 2

    # --- Delivery Risk: late rate + avg delay + transit stddev, normalised & averaged
    df["late_rate_norm"] = min_max_normalize(df["late_rate_pct"].fillna(0))
    df["avg_delay_norm"] = min_max_normalize(df["avg_delay_days_when_late"].fillna(0))
    df["transit_var_norm"] = min_max_normalize(df["transit_time_stddev_hours"].fillna(0))
    df["delivery_risk"] = (df["late_rate_norm"] + df["avg_delay_norm"] + df["transit_var_norm"]) / 3

    # --- Seller Risk: revenue-weighted (100 - seller_score), already 0-100
    df["seller_risk"] = df["revenue_weighted_seller_risk"].fillna(df["revenue_weighted_seller_risk"].median())

    df["supply_chain_risk"] = (
        df["demand_risk"] * WEIGHTS["demand_risk"]
        + df["delivery_risk"] * WEIGHTS["delivery_risk"]
        + df["seller_risk"] * WEIGHTS["seller_risk"]
    ).round(1)
    df["risk_tier"] = df["supply_chain_risk"].apply(classify_risk)

    df = df.sort_values("supply_chain_risk", ascending=False)

    out_cols = [
        "category_en", "n_orders", "total_revenue",
        "coefficient_of_variation", "demand_class", "anomaly_frequency", "demand_risk",
        "late_rate_pct", "avg_delay_days_when_late", "transit_time_stddev_hours", "delivery_risk",
        "revenue_weighted_seller_risk", "seller_risk",
        "supply_chain_risk", "risk_tier",
    ]
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    df[out_cols].round(2).to_csv(EXPORTS_DIR / "supply_chain_risk_index.csv", index=False)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    tier_counts = df["risk_tier"].value_counts().reindex(["LOW RISK", "MEDIUM RISK", "HIGH RISK"]).fillna(0).astype(int)
    lines = [
        "# Supply Chain Risk Index",
        "",
        "Supply Chain Risk = 40% Demand Risk + 35% Delivery Risk + 25% Seller Risk, "
        "each component min-max normalised to 0-100 across categories before blending.",
        "",
        "## Risk tier distribution",
        "",
        tier_counts.to_markdown(),
        "",
        "## Highest-risk categories (management should investigate first)",
        "",
        df[out_cols].head(10).round(2).to_markdown(index=False),
    ]
    (REPORTS_DIR / "supply_chain_risk_index.md").write_text("\n".join(lines), encoding="utf-8")

    print(tier_counts)
    print(df[["category_en", "supply_chain_risk", "risk_tier"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
