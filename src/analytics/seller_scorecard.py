"""
Seller Performance Scorecard.

v2 method (each step fixes a v1 problem):
  1. Metrics at seller-ORDER grain (v1 counted items, so multi-unit orders
     weighed more).
  2. Only sellers with >= MIN_SELLER_ORDERS orders are ranked. Everyone else
     is listed as "Insufficient volume" with their order count, rather than
     disappearing (v1 cut-off: 5 orders).
  3. Rates are shrunk toward the platform rate with an empirical-Bayes prior,
     so a seller's score reflects evidence, not luck in a small sample.
  4. Components are percentile-ranked, not min-max scaled, so one extreme
     seller cannot compress everyone else.
  5. Tiers are explicitly RELATIVE (top 25% / middle 50% / next 15% /
     bottom 10%). Separately, `late_rate_flag` is an ABSOLUTE test: the
     seller's 95% Wilson lower bound on late rate exceeds the platform rate.
"""

import duckdb
import numpy as np
import pandas as pd

from src.analytics.stats import (
    assign_quantile_tiers, beta_prior_mom, mean_prior_strength,
    percentile_score, shrink_mean, shrink_proportion, wilson_interval,
)
from src.config import MIN_SELLER_ORDERS, Settings
from src.db import query_file

# (metric column, weight, higher_is_better)
COMPONENTS = [
    ("on_time_rate_adj", 0.30, True),
    ("avg_fulfilment_days", 0.25, False),
    ("cancellation_rate_adj", 0.20, False),
    ("avg_review_adj", 0.15, True),
    ("freight_to_price_pct", 0.10, False),
]
TIERS = [("Excellent", 0.25), ("Good", 0.50), ("At Risk", 0.15), ("Critical", 0.10)]
INSUFFICIENT = "Insufficient volume"


def build_scorecard(raw: pd.DataFrame, reviews: pd.DataFrame,
                    min_orders: int = MIN_SELLER_ORDERS) -> tuple[pd.DataFrame, dict]:
    # Fixed input order: tier assignment breaks score ties by position, and
    # SQL GROUP BY output order is not guaranteed.
    df = raw.sort_values("seller_id").reset_index(drop=True)
    df["n_on_time"] = df["n_delivered"] - df["n_late"]
    df["late_rate_raw"] = df["n_late"] / df["n_delivered"].replace(0, np.nan)
    df["missed_limit_rate_raw"] = df["n_missed_shipping_limit"] / df["n_with_handover"].replace(0, np.nan)
    df["eligible"] = df["n_orders"] >= min_orders

    platform_late = df["n_late"].sum() / df["n_delivered"].sum()
    elig = df[df["eligible"] & (df["n_delivered"] > 0)]

    # Empirical-Bayes priors are estimated on eligible sellers only, then
    # applied to everyone (so the CSV still shows adjusted values for small sellers).
    a_late, b_late = beta_prior_mom(elig["n_late"], elig["n_delivered"])
    a_can, b_can = beta_prior_mom(elig["n_canceled"], elig["n_orders"])
    df["late_rate_adj"] = shrink_proportion(df["n_late"], df["n_delivered"], a_late, b_late)
    df["on_time_rate_adj"] = 1 - df["late_rate_adj"]
    df["cancellation_rate_adj"] = shrink_proportion(df["n_canceled"], df["n_orders"], a_can, b_can)

    k_review = mean_prior_strength(reviews["review_score"], reviews["seller_id"])
    global_review = reviews["review_score"].mean()
    df["avg_review_adj"] = shrink_mean(df["avg_review_score"].fillna(global_review),
                                       df["n_reviews"], global_review, k_review)

    lo, hi = wilson_interval(df["n_late"], df["n_delivered"])
    df["late_rate_ci_low"], df["late_rate_ci_high"] = lo, hi
    df["late_rate_flag"] = df["eligible"] & (df["late_rate_ci_low"] > platform_late)

    scored = df[df["eligible"]].copy()
    for col, _, _ in COMPONENTS:
        scored[col] = scored[col].fillna(scored[col].median())
    scored["seller_score"] = sum(
        percentile_score(scored[col], higher_is_better=hib) * w for col, w, hib in COMPONENTS
    ).round(1)
    scored["performance_tier"] = assign_quantile_tiers(scored["seller_score"], TIERS)

    df = df.merge(scored[["seller_id", "seller_score", "performance_tier"]], on="seller_id", how="left")
    df["performance_tier"] = df["performance_tier"].fillna(INSUFFICIENT)
    df["seller_risk_score"] = (100 - df["seller_score"]).round(1)

    params = {
        "min_orders": min_orders,
        "platform_late_rate": platform_late,
        "late_prior": (a_late, b_late),
        "cancel_prior": (a_can, b_can),
        "review_prior_strength": k_review,
        "n_sellers": len(df),
        "n_scored": int(df["eligible"].sum()),
    }
    return df.sort_values(["seller_score", "n_orders", "seller_id"],
                          ascending=[False, False, True]), params


OUT_COLS = [
    "seller_id", "state", "region", "n_orders", "n_items", "total_revenue",
    "n_delivered", "n_late", "late_rate_raw", "late_rate_ci_low", "late_rate_ci_high",
    "late_rate_adj", "otd_pct", "avg_fulfilment_days", "cancellation_rate_pct",
    "missed_limit_rate_raw", "avg_review_score", "avg_review_adj", "freight_to_price_pct",
    "seller_score", "performance_tier", "late_rate_flag", "seller_risk_score",
]


def run(con: duckdb.DuckDBPyConnection, settings: Settings) -> pd.DataFrame:
    raw = query_file(con, "kpis/04_seller_raw_metrics.sql", 0)
    reviews = query_file(con, "kpis/04_seller_raw_metrics.sql", 1)
    df, params = build_scorecard(raw, reviews)

    # Presentation columns (percentages) kept alongside the fractions.
    df["otd_pct"] = (100 * df["on_time_rate_adj"]).round(2)
    df["cancellation_rate_pct"] = (100 * df["cancellation_rate_adj"]).round(2)
    out = df[OUT_COLS].round(4)

    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(settings.exports_dir / "seller_scorecard.csv", index=False)
    con.register("seller_scores_df", out[out["seller_score"].notna()])
    con.execute("CREATE OR REPLACE TABLE gold.seller_scores AS SELECT * FROM seller_scores_df")
    con.unregister("seller_scores_df")

    write_report(out, params, settings)
    return out


def write_report(df: pd.DataFrame, params: dict, settings: Settings) -> None:
    tiers = df["performance_tier"].value_counts().reindex(
        [t for t, _ in TIERS] + [INSUFFICIENT]).fillna(0).astype(int)
    scored = df[df["seller_score"].notna()]
    flagged = scored[scored["late_rate_flag"]].sort_values(
        ["late_rate_ci_low", "seller_id"], ascending=[False, True])
    show = ["seller_id", "state", "n_orders", "late_rate_raw", "late_rate_ci_low",
            "late_rate_ci_high", "late_rate_adj", "avg_fulfilment_days", "avg_review_adj",
            "seller_score", "performance_tier"]
    a, b = params["late_prior"]
    lines = [
        "# Seller Performance Scorecard",
        "",
        f"{params['n_sellers']:,} sellers; **{params['n_scored']:,} ranked** "
        f"(>= {params['min_orders']} distinct orders). The rest are listed in "
        "`data/exports/seller_scorecard.csv` as *Insufficient volume* with their order counts.",
        "",
        "## Method",
        "",
        "- Metrics are computed per seller-order, not per item.",
        f"- Late and cancellation rates are shrunk toward the platform rate with an empirical-Bayes "
        f"Beta prior (late-rate prior = Beta({a:.1f}, {b:.1f}), i.e. worth ~{a + b:.0f} orders). "
        f"Review averages use a prior worth ~{params['review_prior_strength']:.0f} reviews.",
        "- Score = 30% on-time + 25% fulfilment speed + 20% cancellation + 15% review + "
        "10% freight/price, each as a percentile rank (0-100) among ranked sellers.",
        "- **Tiers are relative**: top 25% Excellent, next 50% Good, next 15% At Risk, bottom 10% Critical.",
        f"- **Absolute flag**: `late_rate_flag` is set when the 95% Wilson lower bound of a seller's "
        f"late rate exceeds the platform late rate ({params['platform_late_rate']:.2%}). "
        f"{len(flagged)} ranked sellers are flagged.",
        "",
        "## Tier distribution",
        "",
        tiers.to_markdown(),
        "",
        "## Sellers with a statistically significant late-delivery problem",
        "",
        flagged[show].head(15).to_markdown(index=False) if len(flagged) else "_None._",
        "",
        "## Bottom 10 ranked sellers",
        "",
        scored[show].tail(10).to_markdown(index=False),
        "",
        "## Top 10 ranked sellers",
        "",
        scored[show].head(10).to_markdown(index=False),
        "",
        "Caveat: delivery outcome, fulfilment time and review are recorded per order, so in "
        "multi-seller orders (~1.3%) every seller inherits the order's values.",
    ]
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.reports_dir / "seller_scorecard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(settings: Settings | None = None):
    from src.config import get_settings
    from src.db import connect

    settings = settings or get_settings()
    with connect(settings) as con:
        df = run(con, settings)
    print(df["performance_tier"].value_counts().to_string())
    print(f"  late_rate_flag: {int(df['late_rate_flag'].sum())} sellers")


if __name__ == "__main__":
    main()
