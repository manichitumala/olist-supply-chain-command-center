"""
Phase 5 - Seller Performance Intelligence.

Builds a weighted 0-100 Seller Performance Score from five normalised
metrics, then classifies each seller into Excellent / Good / At Risk /
Critical. This is deliberately NOT a simple revenue ranking.
"""

import pandas as pd

from config import EXPORTS_DIR, REPORTS_DIR, ROOT
from db import get_engine, get_psycopg_connection

RAW_SQL = (ROOT / "sql" / "kpis" / "04_seller_raw_metrics.sql").read_text(encoding="utf-8")

WEIGHTS = {
    "otd_pct": 0.30,                    # higher is better
    "avg_fulfilment_days": 0.25,        # lower is better
    "cancellation_rate_pct": 0.20,      # lower is better
    "avg_review_score": 0.15,           # higher is better
    "avg_freight_to_price_pct": 0.10,   # lower is better
}
LOWER_IS_BETTER = {"avg_fulfilment_days", "cancellation_rate_pct", "avg_freight_to_price_pct"}


def min_max_normalize(series: pd.Series, invert: bool) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(50.0, index=series.index)
    scaled = (series - lo) / (hi - lo) * 100.0
    return 100.0 - scaled if invert else scaled


def classify(score: float) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 60:
        return "At Risk"
    return "Critical"


def build_scorecard() -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql(RAW_SQL, engine)

    # Missing fulfilment/review data (rare) -> fill with the population
    # median rather than dropping the seller from the scorecard entirely.
    for col in WEIGHTS:
        df[col] = df[col].fillna(df[col].median())

    for col in WEIGHTS:
        df[f"{col}_norm"] = min_max_normalize(df[col], invert=col in LOWER_IS_BETTER)

    df["seller_score"] = sum(df[f"{col}_norm"] * w for col, w in WEIGHTS.items())
    df["seller_score"] = df["seller_score"].round(1)
    df["performance_tier"] = df["seller_score"].apply(classify)
    df["seller_risk_score"] = (100 - df["seller_score"]).round(1)

    return df.sort_values("seller_score", ascending=False)


def main():
    df = build_scorecard()

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_cols = [
        "seller_id", "state", "region", "n_orders", "n_items", "total_revenue",
        "otd_pct", "avg_fulfilment_days", "cancellation_rate_pct",
        "avg_review_score", "avg_freight_to_price_pct",
        "seller_score", "performance_tier", "seller_risk_score",
    ]
    df[out_cols].to_csv(EXPORTS_DIR / "seller_scorecard.csv", index=False)

    # Persisted to gold so downstream SQL (category risk index) can join to it.
    conn = get_psycopg_connection()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS gold")
        cur.execute("DROP TABLE IF EXISTS gold.seller_scores")
    conn.close()
    df[out_cols].to_sql("seller_scores", get_engine(), schema="gold", if_exists="replace", index=False)
    with get_engine().begin() as c:
        c.exec_driver_sql("ALTER TABLE gold.seller_scores ADD PRIMARY KEY (seller_id)")

    tier_summary = df["performance_tier"].value_counts().reindex(
        ["Excellent", "Good", "At Risk", "Critical"]
    ).fillna(0).astype(int)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Seller Performance Scorecard",
        "",
        f"Scored {len(df):,} sellers with >= 5 orders using: "
        "30% On-Time Delivery, 25% Fulfilment Speed, 20% Cancellation Rate, "
        "15% Review Score, 10% Freight Efficiency (all min-max normalised 0-100 "
        "first; 'lower is better' metrics are inverted before weighting).",
        "",
        "## Tier distribution",
        "",
        tier_summary.to_markdown(),
        "",
        "## Bottom 10 sellers (highest operational risk)",
        "",
        df[out_cols].tail(10).to_markdown(index=False),
        "",
        "## Top 10 sellers",
        "",
        df[out_cols].head(10).to_markdown(index=False),
    ]
    (REPORTS_DIR / "seller_scorecard.md").write_text("\n".join(lines), encoding="utf-8")

    print(tier_summary)
    print(f"Scorecard for {len(df)} sellers written to data/exports/seller_scorecard.csv")


if __name__ == "__main__":
    main()
