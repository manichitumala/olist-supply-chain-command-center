"""
Root-cause analysis of late deliveries.

  * Stage comparison: where do late orders lose time?
  * Seller drill-down: ranked sellers whose late rate is significantly above
    the platform rate (from the scorecard, with confidence intervals).
  * Transport hotspots: distance band x customer region.
  * Hypothesis test: do multi-seller orders have worse outcomes?

v2 fix: multi-seller rates are order-weighted. v1 averaged the 2-seller and
3+-seller band RATES without weights, letting a 59-order band pull the
headline to 0.7%. The verdict text is now generated from the test results
instead of being hard-coded.
"""

import duckdb
import pandas as pd

from src.analytics.stats import mann_whitney, two_proportion_ztest, wilson_interval
from src.config import Settings
from src.db import query_file

ALPHA = 0.05


def complexity_table(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute("""
        SELECT sellers_per_order_band,
               COUNT(*) AS n_orders,
               SUM((otd_status = 'Late')::INT) AS n_late,
               ROUND(AVG(lead_time_days), 2) AS avg_lead_time_days,
               ROUND(AVG(review_score), 2) AS avg_review_score,
               COUNT(review_score) AS n_reviews
        FROM gold.fact_order
        WHERE is_delivered
        GROUP BY sellers_per_order_band
        ORDER BY sellers_per_order_band
    """).df()
    lo, hi = wilson_interval(df["n_late"], df["n_orders"])
    df["late_rate_pct"] = (100 * df["n_late"] / df["n_orders"]).round(2)
    df["late_ci_low_pct"], df["late_ci_high_pct"] = (100 * lo).round(2), (100 * hi).round(2)
    return df


def multi_seller_test(con: duckdb.DuckDBPyConnection) -> dict:
    """Single-seller vs 2+ seller orders, pooled (order-weighted)."""
    g = con.execute("""
        SELECT is_multi_seller_order AS multi,
               COUNT(*) AS n, SUM((otd_status = 'Late')::INT) AS k
        FROM gold.fact_order WHERE is_delivered GROUP BY 1
    """).df().set_index("multi")
    late = two_proportion_ztest(int(g.loc[True, "k"]), int(g.loc[True, "n"]),
                                int(g.loc[False, "k"]), int(g.loc[False, "n"]))
    reviews = con.execute("""
        SELECT is_multi_seller_order AS multi, review_score
        FROM gold.fact_order WHERE is_delivered AND review_score IS NOT NULL
    """).df()
    multi_r = reviews.loc[reviews["multi"], "review_score"]
    single_r = reviews.loc[~reviews["multi"], "review_score"]
    review = mann_whitney(multi_r, single_r)
    return {
        "n_multi": int(g.loc[True, "n"]), "n_single": int(g.loc[False, "n"]),
        "late_multi": late["p1"], "late_single": late["p2"], "late_p": late["p_value"],
        "review_multi": float(multi_r.mean()), "review_single": float(single_r.mean()),
        "review_p": review["p_value"],
    }


def verdict(t: dict) -> str:
    late_sig = t["late_p"] < ALPHA
    review_sig = t["review_p"] < ALPHA
    late_dir = "lower" if t["late_multi"] < t["late_single"] else "higher"
    review_dir = "lower" if t["review_multi"] < t["review_single"] else "higher"
    parts = [
        f"Multi-seller orders are {t['n_multi'] / (t['n_multi'] + t['n_single']):.1%} of delivered orders "
        f"(n={t['n_multi']:,}).",
        f"Late rate: {t['late_multi']:.2%} vs {t['late_single']:.2%} for single-seller orders "
        f"({late_dir}; two-proportion z-test p={t['late_p']:.2g}"
        + (", significant)." if late_sig else ", not significant)."),
        f"Average review: {t['review_multi']:.2f} vs {t['review_single']:.2f} "
        f"({review_dir}; Mann-Whitney p={t['review_p']:.2g}"
        + (", significant)." if review_sig else ", not significant)."),
    ]
    if late_sig and review_sig and late_dir == "lower" and review_dir == "lower":
        parts.append(
            "So the hypothesis that multi-seller orders are delivered late more often is rejected, "
            "yet customers rate them worse. This is an association, not a cause: these orders differ "
            "in basket size, sellers and categories. Split or partial deliveries are a plausible "
            "explanation, but Olist has no per-shipment timestamps to test it.")
    return " ".join(parts)


def run(con: duckdb.DuckDBPyConnection, settings: Settings) -> dict:
    stages = query_file(con, "kpis/02_fulfilment_kpis.sql", 2)
    complexity = complexity_table(con)
    test = multi_seller_test(con)

    scorecard = pd.read_csv(settings.exports_dir / "seller_scorecard.csv")
    worst_sellers = (scorecard[scorecard["late_rate_flag"] == True]  # noqa: E712
                     .sort_values(["late_rate_ci_low", "seller_id"], ascending=[False, True]).head(15))
    worst_sellers = worst_sellers.assign(
        late_rate_pct=(100 * worst_sellers["late_rate_raw"]).round(2),
        late_ci_low_pct=(100 * worst_sellers["late_rate_ci_low"]).round(2),
        late_ci_high_pct=(100 * worst_sellers["late_rate_ci_high"]).round(2),
    )[["seller_id", "state", "n_orders", "n_delivered", "n_late", "late_rate_pct",
       "late_ci_low_pct", "late_ci_high_pct", "avg_fulfilment_days", "missed_limit_rate_raw"]]

    transport = con.execute("""
        SELECT distance_band, customer_region AS region,
               COUNT(*) AS n_orders,
               SUM((otd_status = 'Late')::INT) AS n_late,
               ROUND(AVG(transit_time_hours) / 24.0, 2) AS avg_transit_days
        FROM gold.fact_order
        WHERE is_delivered
        GROUP BY ALL
        HAVING COUNT(*) >= 100
    """).df()
    lo, hi = wilson_interval(transport["n_late"], transport["n_orders"])
    transport["late_rate_pct"] = (100 * transport["n_late"] / transport["n_orders"]).round(2)
    transport["late_ci_low_pct"], transport["late_ci_high_pct"] = (100 * lo).round(2), (100 * hi).round(2)
    transport = transport.sort_values(["late_rate_pct", "n_orders", "distance_band", "region"],
                                      ascending=[False, False, True, True]).head(15)

    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    worst_sellers.to_csv(settings.exports_dir / "root_cause_worst_sellers.csv", index=False)
    transport.to_csv(settings.exports_dir / "root_cause_transport_delay.csv", index=False)
    complexity.to_csv(settings.exports_dir / "root_cause_multi_seller_complexity.csv", index=False)

    s = stages.set_index("otd_status")
    transit_x = s.loc["Late", "avg_transit_days"] / s.loc["On Time", "avg_transit_days"]
    fulfil_x = s.loc["Late", "avg_fulfilment_days"] / s.loc["On Time", "avg_fulfilment_days"]
    text = verdict(test)

    lines = [
        "# Root-Cause Analysis: Why Are Orders Late?",
        "",
        "Late = delivered after the promised calendar date. Population: delivered orders whose "
        "timestamps pass the silver sequence checks.",
        "",
        "## Stage comparison, on-time vs late",
        "",
        stages.to_markdown(index=False),
        "",
        f"Late orders spend {transit_x:.1f}x longer in transit and {fulfil_x:.1f}x longer in seller "
        "fulfilment than on-time orders. Transport is the larger contributor; seller fulfilment "
        "is secondary.",
        "",
        "## Sellers with a significantly high late rate",
        "",
        "Ranked sellers (>= 30 orders) whose 95% Wilson lower bound on late rate is above the "
        "platform rate. Sorted by that lower bound, i.e. by strength of evidence.",
        "",
        worst_sellers.to_markdown(index=False) if len(worst_sellers) else "_None._",
        "",
        "## Transport hotspots (distance band x customer region, >= 100 orders)",
        "",
        transport.to_markdown(index=False),
        "",
        "## Hypothesis: do multi-seller orders have worse outcomes?",
        "",
        complexity.to_markdown(index=False),
        "",
        f"**Verdict:** {text}",
    ]
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.reports_dir / "root_cause_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"test": test, "verdict": text}


def main(settings: Settings | None = None):
    from src.config import get_settings
    from src.db import connect

    settings = settings or get_settings()
    with connect(settings) as con:
        out = run(con, settings)
    print(out["verdict"])


if __name__ == "__main__":
    main()
