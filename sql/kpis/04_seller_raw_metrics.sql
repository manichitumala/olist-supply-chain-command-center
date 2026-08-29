-- DASHBOARD 4 — SELLER PERFORMANCE (raw inputs)
-- One row per seller with the raw metrics that python/seller_scorecard.py
-- normalises to 0-100 and blends into the weighted Seller Performance Score.
-- NOTE: fulfilment_time and review_score are captured at ORDER grain in the
-- source data (Olist does not timestamp shipments per seller), so for
-- multi-seller orders every seller in that order inherits the same
-- order-level values. This is a known limitation, documented in the README.

SELECT
    foi.seller_key AS seller_id,
    ds.state,
    ds.region,
    COUNT(DISTINCT foi.order_id) AS n_orders,
    COUNT(*) AS n_items,
    ROUND(SUM(foi.price)::numeric, 2) AS total_revenue,

    -- On-time delivery rate for orders touched by this seller
    ROUND(100.0 * SUM(CASE WHEN fd.otd_status = 'On Time' THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN fd.otd_status IN ('On Time','Late') THEN 1 ELSE 0 END), 0), 2)
        AS otd_pct,

    -- Fulfilment speed (order-level, see note above)
    ROUND(AVG(fd.fulfilment_time_hours) / 24.0, 2) AS avg_fulfilment_days,

    -- Cancellation rate across this seller's items
    ROUND(100.0 * SUM(CASE WHEN foi.order_status = 'canceled' THEN 1 ELSE 0 END)
        / COUNT(*), 2) AS cancellation_rate_pct,

    -- Customer satisfaction
    ROUND(AVG(fd.review_score)::numeric, 2) AS avg_review_score,

    -- Freight efficiency: freight cost as a percentage of item price (lower = better)
    ROUND(100.0 * AVG(foi.freight_value / NULLIF(foi.price, 0))::numeric, 2)
        AS avg_freight_to_price_pct

FROM gold.fact_order_item foi
JOIN gold.dim_seller ds ON ds.seller_key = foi.seller_key
LEFT JOIN gold.fact_delivery fd ON fd.order_id = foi.order_id
GROUP BY foi.seller_key, ds.state, ds.region
HAVING COUNT(DISTINCT foi.order_id) >= 5;
