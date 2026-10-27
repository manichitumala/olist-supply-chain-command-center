-- Category-level delivery and seller-risk inputs for src/analytics/risk_index.py.
-- Grain fix: an order counts ONCE per category it contains (v1 counted once
-- per item, so multi-unit orders were over-weighted in late rates).
-- Requires gold.seller_scores (written by seller_scorecard.py).
WITH category_orders AS (
    SELECT DISTINCT dp.category_en, foi.order_id
    FROM gold.fact_order_item foi
    JOIN gold.dim_product dp ON dp.product_key = foi.product_key
    WHERE foi.is_revenue_status
),
delivery AS (
    SELECT
        co.category_en,
        COUNT(*) AS n_orders,
        SUM(fo.is_delivered::INT) AS n_delivered,
        SUM((fo.otd_status = 'Late')::INT) AS n_late,
        100.0 * AVG(CASE WHEN fo.is_delivered THEN (fo.otd_status = 'Late')::INT END) AS late_rate_pct,
        AVG(CASE WHEN fo.otd_status = 'Late' THEN fo.days_late END) AS avg_delay_days_when_late,
        STDDEV_SAMP(fo.transit_time_hours) AS transit_time_stddev_hours
    FROM category_orders co
    JOIN gold.fact_order fo ON fo.order_id = co.order_id
    GROUP BY co.category_en
),
seller_risk AS (
    -- Revenue-weighted (100 - seller_score) over SCORED sellers only, plus
    -- the share of category revenue that this covers.
    SELECT
        dp.category_en,
        SUM(foi.price * (100 - sc.seller_score)) / NULLIF(SUM(CASE WHEN sc.seller_score IS NOT NULL THEN foi.price END), 0)
            AS revenue_weighted_seller_risk,
        SUM(CASE WHEN sc.seller_score IS NOT NULL THEN foi.price END) / NULLIF(SUM(foi.price), 0)
            AS scored_revenue_share
    FROM gold.fact_order_item foi
    JOIN gold.dim_product dp ON dp.product_key = foi.product_key
    LEFT JOIN gold.seller_scores sc ON sc.seller_id = foi.seller_key
    WHERE foi.is_revenue_status
    GROUP BY dp.category_en
)
SELECT d.*, s.revenue_weighted_seller_risk, s.scored_revenue_share
FROM delivery d
LEFT JOIN seller_risk s USING (category_en)
WHERE d.n_orders >= 100;
