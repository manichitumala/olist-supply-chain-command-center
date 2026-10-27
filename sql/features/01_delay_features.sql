-- DELAY-PREDICTION FEATURES
-- Prediction moment: PAYMENT APPROVAL (order.approved_ts).
-- Every feature must be knowable at that moment:
--   * the order itself, its items, payment and the promised delivery date
--   * seller / route history built ONLY from orders DELIVERED before this
--     order was PURCHASED (point-in-time, via running sums over an event
--     stream - never the seller's final, whole-period score)
--   * platform load: orders placed in the 7 days before this one
-- Never used: carrier handover, delivery timestamps, transit/fulfilment
-- durations, reviews - all of these happen after the prediction moment.
--
-- Population: delivered orders in the analysis window with an approval
-- timestamp. Label: delivered after the promised calendar date.

WITH orders AS (
    SELECT * FROM gold.fact_order
),
primary_seller AS (
    -- The seller holding the largest share of item value represents the order.
    SELECT DISTINCT ON (order_id) order_id, seller_key
    FROM gold.fact_seller_order
    ORDER BY order_id, item_revenue DESC, seller_key
),
order_keys AS (
    SELECT o.order_id, o.purchase_ts, o.delivered_ts, o.is_delivered,
           (o.otd_status = 'Late')::INT AS is_late,
           ps.seller_key,
           o.customer_state || '>' || s.state AS route
    FROM orders o
    JOIN primary_seller ps USING (order_id)
    JOIN gold.dim_seller s ON s.seller_key = ps.seller_key
),

-- ---------------------------------------------------------------- history
-- Event stream: one "delivery" event per delivered order (adds to history)
-- and one "query" per order at its purchase time (reads history so far).
-- At equal timestamps queries sort first, so an order never sees a
-- delivery that happened at the same instant as its purchase.
seller_stream AS (
    SELECT seller_key AS k, delivered_ts AS ts, 1 AS kind, NULL AS order_id,
           1 AS d, is_late AS l
    FROM order_keys WHERE is_delivered
    UNION ALL
    SELECT seller_key, purchase_ts, 0, order_id, 0, 0 FROM order_keys
),
seller_hist AS (
    SELECT order_id, prior_delivered AS seller_prior_delivered, prior_late AS seller_prior_late
    FROM (
        SELECT order_id, kind,
               SUM(d) OVER w AS prior_delivered,
               SUM(l) OVER w AS prior_late
        FROM seller_stream
        WINDOW w AS (PARTITION BY k ORDER BY ts, kind ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    ) WHERE kind = 0
),
route_stream AS (
    SELECT route AS k, delivered_ts AS ts, 1 AS kind, NULL AS order_id, 1 AS d, is_late AS l
    FROM order_keys WHERE is_delivered
    UNION ALL
    SELECT route, purchase_ts, 0, order_id, 0, 0 FROM order_keys
),
route_hist AS (
    SELECT order_id, prior_delivered AS route_prior_delivered, prior_late AS route_prior_late
    FROM (
        SELECT order_id, kind,
               SUM(d) OVER w AS prior_delivered,
               SUM(l) OVER w AS prior_late
        FROM route_stream
        WINDOW w AS (PARTITION BY k ORDER BY ts, kind ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    ) WHERE kind = 0
),
-- Recent conditions (time-windowed history). Late rates shift a lot between
-- months (the Feb-Mar 2018 spike), so the model needs to know whether the
-- platform - and this seller - are currently having a bad spell.
platform_stream AS (
    SELECT delivered_ts AS ts, 1 AS kind, NULL AS order_id, 1 AS d, is_late AS l
    FROM order_keys WHERE is_delivered
    UNION ALL
    SELECT purchase_ts, 0, order_id, 0, 0 FROM order_keys
),
platform_recent AS (
    SELECT order_id, recent_d AS platform_delivered_30d, recent_l AS platform_late_30d
    FROM (
        SELECT order_id, kind,
               SUM(d) OVER w AS recent_d, SUM(l) OVER w AS recent_l
        FROM platform_stream
        WINDOW w AS (ORDER BY ts RANGE BETWEEN INTERVAL 30 DAY PRECEDING AND CURRENT ROW)
    ) WHERE kind = 0
),
seller_recent AS (
    SELECT order_id, recent_d AS seller_delivered_90d, recent_l AS seller_late_90d
    FROM (
        SELECT order_id, kind,
               SUM(d) OVER w AS recent_d, SUM(l) OVER w AS recent_l
        FROM seller_stream
        WINDOW w AS (PARTITION BY k ORDER BY ts RANGE BETWEEN INTERVAL 90 DAY PRECEDING AND CURRENT ROW)
    ) WHERE kind = 0
),
seller_volume AS (
    -- orders the seller had received (any status) before this purchase
    SELECT order_id,
           COUNT(*) OVER (PARTITION BY seller_key ORDER BY purchase_ts, order_id
                          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS seller_prior_orders
    FROM order_keys
),
platform_load AS (
    SELECT order_id,
           COUNT(*) OVER (ORDER BY purchase_ts
                          RANGE BETWEEN INTERVAL 7 DAY PRECEDING AND CURRENT ROW) - 1 AS orders_prev_7d
    FROM orders
),

-- ---------------------------------------------------------------- order content
items AS (
    SELECT f.order_id,
           SUM(p.weight_g) AS total_weight_g,
           SUM(p.volume_cm3) AS total_volume_cm3,
           COUNT(DISTINCT p.category_en) AS n_categories,
           arg_max(p.category_en, f.price) AS main_category,
           MIN(f.shipping_limit_ts) AS first_shipping_limit_ts
    FROM gold.fact_order_item f
    JOIN gold.dim_product p ON p.product_key = f.product_key
    GROUP BY f.order_id
),
pay AS (
    SELECT order_id,
           arg_max(payment_type, payment_value) AS payment_type,
           MAX(payment_installments) AS max_installments,
           COUNT(*) AS n_payments
    FROM silver.order_payments
    GROUP BY order_id
)

SELECT
    o.order_id,
    o.purchase_ts,
    o.approved_ts,
    k.seller_key,
    (o.otd_status = 'Late')::INT AS is_late,

    -- timing & promise
    date_diff('day', CAST(o.purchase_ts AS DATE), CAST(o.estimated_ts AS DATE)) AS promised_days,
    (epoch(o.approved_ts) - epoch(o.purchase_ts)) / 3600.0 AS approval_hours,
    (epoch(i.first_shipping_limit_ts) - epoch(o.approved_ts)) / 86400.0 AS days_to_shipping_limit,
    month(o.purchase_ts) AS purchase_month,
    isodow(o.purchase_ts) AS purchase_dow,
    hour(o.purchase_ts) AS purchase_hour,

    -- order content
    o.n_items,
    o.n_distinct_sellers,
    o.items_value,
    o.freight_value,
    o.freight_value / NULLIF(o.items_value, 0) AS freight_ratio,
    i.total_weight_g,
    i.total_volume_cm3,
    i.n_categories,
    i.main_category,
    p.payment_type,
    p.max_installments,
    p.n_payments,

    -- geography
    o.customer_state,
    s.state AS seller_state,
    (o.customer_state = s.state)::INT AS same_state,
    o.avg_distance_km AS distance_km,

    -- point-in-time history
    sh.seller_prior_delivered,
    sh.seller_prior_late,
    sv.seller_prior_orders,
    rh.route_prior_delivered,
    rh.route_prior_late,
    pl.orders_prev_7d,
    pr.platform_delivered_30d,
    pr.platform_late_30d,
    sr.seller_delivered_90d,
    sr.seller_late_90d,
    o.delivered_ts       -- NOT a feature: used only to decide when a label becomes known
FROM orders o
JOIN order_keys k USING (order_id)
JOIN gold.dim_seller s ON s.seller_key = k.seller_key
JOIN items i USING (order_id)
LEFT JOIN pay p USING (order_id)
JOIN seller_hist sh USING (order_id)
JOIN route_hist rh USING (order_id)
JOIN seller_volume sv USING (order_id)
JOIN platform_load pl USING (order_id)
JOIN platform_recent pr USING (order_id)
JOIN seller_recent sr USING (order_id)
WHERE o.is_delivered
  AND o.approved_ts IS NOT NULL
  AND o.is_in_analysis_window
ORDER BY o.purchase_ts, o.order_id;
