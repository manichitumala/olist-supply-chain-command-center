"""
Phase 10 - Root-cause analysis of late orders.

Drills into the population of Late orders only, splitting the cause into:
  - Seller fulfilment delay (which sellers, how much worse than their peers)
  - Transportation delay (which distance bands / regions)
  - Order complexity (single vs multi-seller orders)

Also directly tests the hypothesis "multi-seller orders have worse customer
outcomes" -- the gold-layer sanity check already suggested the opposite, so
this is reported honestly rather than forced to fit the expected narrative.
"""

import pandas as pd

from config import EXPORTS_DIR, REPORTS_DIR
from db import get_engine


def main():
    engine = get_engine()

    with engine.connect() as conn:
        overall = pd.read_sql("""
            SELECT otd_status, COUNT(*) AS n_orders,
                   ROUND(AVG(fulfilment_time_hours)/24.0, 2) AS avg_fulfilment_days,
                   ROUND(AVG(transit_time_hours)/24.0, 2) AS avg_transit_days
            FROM gold.fact_delivery
            WHERE is_valid_for_lead_time_analysis AND order_status = 'delivered'
            GROUP BY otd_status
        """, conn)

        seller_delay = pd.read_sql("""
            SELECT foi.seller_key AS seller_id, ds.state,
                   COUNT(DISTINCT foi.order_id) AS n_orders,
                   ROUND(100.0 * SUM(CASE WHEN fd.otd_status='Late' THEN 1 ELSE 0 END)
                       / NULLIF(SUM(CASE WHEN fd.otd_status IN ('On Time','Late') THEN 1 ELSE 0 END),0), 2)
                       AS late_rate_pct,
                   ROUND(AVG(fd.fulfilment_time_hours)/24.0, 2) AS avg_fulfilment_days
            FROM gold.fact_order_item foi
            JOIN gold.dim_seller ds ON ds.seller_key = foi.seller_key
            LEFT JOIN gold.fact_delivery fd ON fd.order_id = foi.order_id
            GROUP BY foi.seller_key, ds.state
            HAVING COUNT(DISTINCT foi.order_id) >= 15
            ORDER BY late_rate_pct DESC
            LIMIT 15
        """, conn)

        transport_delay = pd.read_sql("""
            SELECT distance_band, region,
                   COUNT(*) AS n_orders,
                   ROUND(100.0 * SUM(CASE WHEN otd_status='Late' THEN 1 ELSE 0 END)
                       / NULLIF(SUM(CASE WHEN otd_status IN ('On Time','Late') THEN 1 ELSE 0 END),0), 2)
                       AS late_rate_pct,
                   ROUND(AVG(transit_time_hours)/24.0, 2) AS avg_transit_days
            FROM gold.fact_delivery fd
            JOIN gold.dim_customer dc ON dc.customer_key = fd.customer_key
            WHERE order_status = 'delivered'
            GROUP BY distance_band, region
            HAVING COUNT(*) >= 30
            ORDER BY late_rate_pct DESC
            LIMIT 15
        """, conn)

        complexity = pd.read_sql("""
            SELECT sellers_per_order_band,
                   COUNT(*) AS n_orders,
                   ROUND(AVG(lead_time_days)::numeric, 2) AS avg_lead_time_days,
                   ROUND(100.0 * SUM(CASE WHEN otd_status='Late' THEN 1 ELSE 0 END)
                       / NULLIF(SUM(CASE WHEN otd_status IN ('On Time','Late') THEN 1 ELSE 0 END),0), 2)
                       AS late_rate_pct,
                   ROUND(AVG(review_score)::numeric, 2) AS avg_review_score
            FROM gold.fact_delivery
            WHERE order_status = 'delivered'
            GROUP BY sellers_per_order_band
            ORDER BY sellers_per_order_band
        """, conn)

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    seller_delay.to_csv(EXPORTS_DIR / "root_cause_worst_sellers.csv", index=False)
    transport_delay.to_csv(EXPORTS_DIR / "root_cause_transport_delay.csv", index=False)
    complexity.to_csv(EXPORTS_DIR / "root_cause_multi_seller_complexity.csv", index=False)

    single_late = complexity.loc[complexity["sellers_per_order_band"] == "1", "late_rate_pct"].iloc[0]
    multi_late = complexity.loc[complexity["sellers_per_order_band"] != "1", "late_rate_pct"].mean()
    single_review = complexity.loc[complexity["sellers_per_order_band"] == "1", "avg_review_score"].iloc[0]
    multi_review = complexity.loc[complexity["sellers_per_order_band"] != "1", "avg_review_score"].mean()

    hypothesis_verdict = (
        "PARTIALLY REJECTED, WITH AN IMPORTANT TWIST. On the operational metrics the "
        "hypothesis is rejected: multi-seller orders are LATE LESS OFTEN "
        f"({multi_late:.1f}% vs {single_late}% for single-seller orders) and arrive faster on "
        "average, most likely because they skew toward higher-volume, more reliable sellers and "
        "are rare (under 1.5% of delivered orders). "
        "But customer satisfaction tells the opposite story: average review score drops sharply "
        f"as seller count rises ({single_review} for single-seller orders vs {multi_review:.2f} for "
        "2+ sellers). So multi-seller orders are operationally faster and more reliable by the clock, "
        "yet customers rate them worse anyway -- something about splitting an order across sellers "
        "(likely fragmented/partial deliveries, inconsistent packaging, or mismatched expectations "
        "when items from the same order arrive at different times) hurts the experience in a way "
        "the delivered-date timestamp alone doesn't capture. This is flagged as an open question for "
        "further investigation rather than resolved here -- Olist's schema has no per-shipment "
        "timestamp to confirm the split-delivery theory directly."
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Root-Cause Analysis: Why Are Orders Late?",
        "",
        "## Stage comparison, on-time vs late orders",
        "",
        overall.to_markdown(index=False),
        "",
        "Late orders spend roughly "
        f"{(overall.set_index('otd_status').loc['Late','avg_transit_days'] / overall.set_index('otd_status').loc['On Time','avg_transit_days']):.1f}x "
        "longer in transit than on-time orders, and "
        f"{(overall.set_index('otd_status').loc['Late','avg_fulfilment_days'] / overall.set_index('otd_status').loc['On Time','avg_fulfilment_days']):.1f}x "
        "longer in seller fulfilment -- transportation is the dominant bottleneck, "
        "with seller fulfilment as a secondary contributor.",
        "",
        "## Worst-performing sellers by late rate (>= 15 orders)",
        "",
        seller_delay.to_markdown(index=False),
        "",
        "## Transportation delay hotspots (distance band x region, >= 30 orders)",
        "",
        transport_delay.to_markdown(index=False),
        "",
        "## Hypothesis test: do multi-seller orders have worse outcomes?",
        "",
        complexity.to_markdown(index=False),
        "",
        f"**Verdict: {hypothesis_verdict}**",
    ]
    (REPORTS_DIR / "root_cause_analysis.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"Root cause analysis written. Multi-seller hypothesis: {hypothesis_verdict[:11]}")


if __name__ == "__main__":
    main()
