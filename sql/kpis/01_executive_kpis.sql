-- DASHBOARD 1 — EXECUTIVE COMMAND CENTER
-- One row of headline KPIs across the whole (delivered-eligible) order base.

SELECT
    COUNT(DISTINCT fd.order_id) AS total_orders,
    ROUND(SUM(fd.total_price)::numeric, 2) AS total_revenue,
    ROUND(100.0 * SUM(CASE WHEN fd.otd_status = 'On Time' THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN fd.otd_status IN ('On Time', 'Late') THEN 1 ELSE 0 END), 0), 2)
        AS on_time_delivery_pct,
    ROUND(AVG(fd.lead_time_days)::numeric, 2) AS avg_delivery_days,
    SUM(CASE WHEN fd.otd_status = 'Late' THEN 1 ELSE 0 END) AS late_orders,
    ROUND(100.0 * SUM(CASE WHEN fd.order_status = 'canceled' THEN 1 ELSE 0 END)
        / COUNT(*), 2) AS cancellation_rate_pct,
    ROUND(AVG(fd.review_score)::numeric, 2) AS avg_review_score
FROM gold.fact_delivery fd;

-- Monthly trend of the same headline metrics, for the executive trend chart.
SELECT
    d.year_month,
    COUNT(*) AS n_orders,
    ROUND(SUM(fd.total_price)::numeric, 2) AS revenue,
    ROUND(100.0 * SUM(CASE WHEN fd.otd_status = 'On Time' THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN fd.otd_status IN ('On Time', 'Late') THEN 1 ELSE 0 END), 0), 2)
        AS on_time_delivery_pct,
    ROUND(AVG(fd.lead_time_days)::numeric, 2) AS avg_delivery_days,
    ROUND(AVG(fd.review_score)::numeric, 2) AS avg_review_score
FROM gold.fact_delivery fd
JOIN gold.dim_date d ON d.date_id = fd.purchase_date_id
GROUP BY d.year_month
ORDER BY d.year_month;
