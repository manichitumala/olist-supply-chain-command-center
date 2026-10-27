-- DASHBOARD 1 - EXECUTIVE COMMAND CENTER
-- Headline KPIs over ALL orders. Each metric states its own population:
--   orders / cancellation rate : every order (incl. the 775 with no items)
--   revenue (GMV)              : item value of orders not cancelled/unavailable
--   on-time / lead time        : delivered orders, judged on calendar dates
SELECT
    COUNT(*) AS total_orders,
    COUNT(DISTINCT customer_unique_id) AS unique_customers,
    ROUND(SUM(CASE WHEN is_revenue_order THEN items_value END), 2) AS total_revenue,
    ROUND(100.0 * AVG(CASE WHEN is_delivered THEN (otd_status = 'On Time')::INT END), 2)
        AS on_time_delivery_pct,
    ROUND(AVG(lead_time_days), 2) AS avg_delivery_days,
    SUM((otd_status = 'Late')::INT) AS late_orders,
    ROUND(100.0 * AVG(is_canceled::INT), 2) AS cancellation_rate_pct,
    ROUND(AVG(review_score), 2) AS avg_review_score
FROM gold.fact_order;

-- Monthly trend, restricted to the analysis window (see src/config.py).
-- n_delivered is reported so a thin month is visible rather than hidden.
SELECT
    strftime(purchase_ts, '%Y-%m') AS year_month,
    COUNT(*) AS n_orders,
    SUM(is_delivered::INT) AS n_delivered,
    ROUND(SUM(CASE WHEN is_revenue_order THEN items_value END), 2) AS revenue,
    ROUND(100.0 * AVG(CASE WHEN is_delivered THEN (otd_status = 'On Time')::INT END), 2)
        AS on_time_delivery_pct,
    ROUND(AVG(lead_time_days), 2) AS avg_delivery_days,
    ROUND(AVG(review_score), 2) AS avg_review_score
FROM gold.fact_order
WHERE is_in_analysis_window
GROUP BY year_month
ORDER BY year_month;
