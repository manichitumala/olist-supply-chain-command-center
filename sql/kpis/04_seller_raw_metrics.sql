-- DASHBOARD 4 - SELLER PERFORMANCE (raw inputs)
-- One row per seller, computed at seller-ORDER grain (gold.fact_seller_order),
-- so an order counts once per seller however many items it contained.
-- src/analytics/seller_scorecard.py applies small-sample shrinkage and the
-- minimum-volume rule; this query returns every seller with counts so that
-- nothing is filtered silently.
--
-- Attribution caveat: delivery outcome, fulfilment time and review are
-- recorded once per order by Olist, so in multi-seller orders (~1.3%) each
-- seller inherits the order's values. missed_shipping_limit uses the
-- seller's own shipping deadline.
SELECT
    so.seller_key AS seller_id,
    ds.state,
    ds.region,
    COUNT(*) AS n_orders,
    SUM(so.n_items) AS n_items,
    ROUND(SUM(CASE WHEN so.is_revenue_order THEN so.item_revenue END), 2) AS total_revenue,

    SUM(so.is_delivered::INT) AS n_delivered,
    SUM((so.otd_status = 'Late')::INT) AS n_late,
    SUM(so.is_canceled::INT) AS n_canceled,
    COUNT(so.missed_shipping_limit) AS n_with_handover,
    SUM(so.missed_shipping_limit::INT) AS n_missed_shipping_limit,

    AVG(so.fulfilment_time_hours) / 24.0 AS avg_fulfilment_days,
    AVG(so.review_score) AS avg_review_score,
    COUNT(so.review_score) AS n_reviews,
    100.0 * SUM(so.freight_value) / NULLIF(SUM(so.item_revenue), 0) AS freight_to_price_pct
FROM gold.fact_seller_order so
JOIN gold.dim_seller ds ON ds.seller_key = so.seller_key
GROUP BY so.seller_key, ds.state, ds.region;

-- Seller-order rows with review scores, used to estimate how much to shrink
-- each seller's average review toward the platform mean.
SELECT seller_key AS seller_id, review_score
FROM gold.fact_seller_order
WHERE review_score IS NOT NULL;
