-- DASHBOARD 5 — DEMAND & RISK INTELLIGENCE (raw inputs)
-- Weekly demand per product category. python/demand_variability.py computes
-- mean, standard deviation, coefficient of variation and per-week Z-scores
-- from this.

SELECT
    dp.category_en,
    DATE_TRUNC('week', d.full_date)::date AS week_start,
    COUNT(*) AS n_items_sold,
    ROUND(SUM(foi.price)::numeric, 2) AS revenue
FROM gold.fact_order_item foi
JOIN gold.dim_product dp ON dp.product_key = foi.product_key
JOIN gold.dim_date d ON d.date_id = foi.purchase_date_id
WHERE foi.order_status NOT IN ('canceled', 'unavailable')
GROUP BY dp.category_en, DATE_TRUNC('week', d.full_date)
ORDER BY dp.category_en, week_start;
