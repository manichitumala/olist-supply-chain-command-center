-- Category-level delivery risk inputs, feeding python/risk_index.py.
SELECT
    dp.category_en,
    COUNT(DISTINCT foi.order_id) AS n_orders,
    ROUND(100.0 * SUM(CASE WHEN fd.otd_status = 'Late' THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN fd.otd_status IN ('On Time','Late') THEN 1 ELSE 0 END), 0), 2)
        AS late_rate_pct,
    ROUND(AVG(CASE WHEN fd.otd_status = 'Late' THEN fd.days_vs_estimate END)::numeric, 2)
        AS avg_delay_days_when_late,
    ROUND(STDDEV(fd.transit_time_hours)::numeric, 2) AS transit_time_stddev_hours,

    -- revenue-weighted seller risk for sellers active in this category
    ROUND((SUM(foi.price * (100 - sc.seller_score)) / NULLIF(SUM(foi.price), 0))::numeric, 2)
        AS revenue_weighted_seller_risk
FROM gold.fact_order_item foi
JOIN gold.dim_product dp ON dp.product_key = foi.product_key
LEFT JOIN gold.fact_delivery fd ON fd.order_id = foi.order_id
LEFT JOIN gold.seller_scores sc ON sc.seller_id = foi.seller_key
WHERE foi.order_status NOT IN ('canceled', 'unavailable')
GROUP BY dp.category_en
HAVING COUNT(DISTINCT foi.order_id) >= 20;
