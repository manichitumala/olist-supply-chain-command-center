"""
Category Supply Chain Risk Index.

    40% Demand risk   (CV + anomaly frequency)
    35% Delivery risk (late rate + avg days late + transit-time variability)
    25% Seller risk   (revenue-weighted 100 - seller_score, scored sellers only)

v2 fixes:
  * Delivery inputs at category-ORDER grain (v1 weighted by items).
  * Components are percentile ranks, not min-max (no outlier compression).
  * Tiers are RELATIVE by construction (top 20% High, next 40% Medium,
    bottom 40% Low). v1 put absolute cut-offs (30/60) on min-max scores,
    which is why it reported "0 High Risk" - an artefact, not a finding.
  * Categories need >= 100 orders and >= MIN_TOTAL_ITEMS demand.
"""

import duckdb
import pandas as pd

from src.analytics.stats import assign_quantile_tiers, percentile_score
from src.config import Settings
from src.db import query_file

WEIGHTS = {"demand_risk": 0.40, "delivery_risk": 0.35, "seller_risk": 0.25}
TIERS = [("HIGH RISK", 0.20), ("MEDIUM RISK", 0.40), ("LOW RISK", 0.40)]


def build_index(demand: pd.DataFrame, delivery: pd.DataFrame) -> pd.DataFrame:
    demand = demand[demand["demand_class"] != "Insufficient data"]
    df = demand.merge(delivery, on="category_en", how="inner")

    df["demand_risk"] = (percentile_score(df["coefficient_of_variation"])
                         + percentile_score(df["anomaly_frequency"])) / 2
    df["delivery_risk"] = (percentile_score(df["late_rate_pct"])
                           + percentile_score(df["avg_delay_days_when_late"].fillna(0))
                           + percentile_score(df["transit_time_stddev_hours"].fillna(0))) / 3
    df["seller_risk"] = percentile_score(
        df["revenue_weighted_seller_risk"].fillna(df["revenue_weighted_seller_risk"].median()))

    df["supply_chain_risk"] = sum(df[c] * w for c, w in WEIGHTS.items()).round(1)
    df["risk_tier"] = assign_quantile_tiers(df["supply_chain_risk"], TIERS)
    return df.sort_values("supply_chain_risk", ascending=False)


OUT_COLS = [
    "category_en", "n_orders", "total_revenue",
    "coefficient_of_variation", "demand_class", "sbc_class", "anomaly_frequency", "demand_risk",
    "n_delivered", "n_late", "late_rate_pct", "avg_delay_days_when_late",
    "transit_time_stddev_hours", "delivery_risk",
    "revenue_weighted_seller_risk", "scored_revenue_share", "seller_risk",
    "supply_chain_risk", "risk_tier",
]


def run(con: duckdb.DuckDBPyConnection, settings: Settings,
        demand: pd.DataFrame | None = None) -> pd.DataFrame:
    if demand is None:
        demand = pd.read_csv(settings.exports_dir / "demand_variability_by_category.csv")
    delivery = query_file(con, "kpis/06_category_delivery_raw.sql")
    df = build_index(demand, delivery)[OUT_COLS].round(2)

    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(settings.exports_dir / "supply_chain_risk_index.csv", index=False)

    tiers = df["risk_tier"].value_counts().reindex([t for t, _ in TIERS]).fillna(0).astype(int)
    lines = [
        "# Supply Chain Risk Index",
        "",
        f"{len(df)} categories (>= 100 orders and enough demand history to classify).",
        "",
        "Risk = 40% Demand + 35% Delivery + 25% Seller. Each input is a percentile rank across "
        "categories, so **the index ranks categories against each other; it is not an absolute "
        "probability of failure**. Tiers: top 20% High, next 40% Medium, bottom 40% Low.",
        "",
        "Seller risk only covers sellers with enough orders to be scored; "
        "`scored_revenue_share` shows how much of each category's revenue that is.",
        "",
        "## Tier distribution",
        "",
        tiers.to_markdown(),
        "",
        "## Highest-risk categories",
        "",
        df.head(10)[["category_en", "n_orders", "late_rate_pct", "coefficient_of_variation",
                     "demand_risk", "delivery_risk", "seller_risk", "scored_revenue_share",
                     "supply_chain_risk", "risk_tier"]].to_markdown(index=False),
    ]
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.reports_dir / "supply_chain_risk_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return df


def main(settings: Settings | None = None):
    from src.config import get_settings
    from src.db import connect

    settings = settings or get_settings()
    with connect(settings) as con:
        df = run(con, settings)
    print(df[["category_en", "supply_chain_risk", "risk_tier"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
