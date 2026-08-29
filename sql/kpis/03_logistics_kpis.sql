-- DASHBOARD 3 — LOGISTICS INTELLIGENCE
-- Distance bands, freight cost, and state-level hotspots.

-- OTD and lead time by distance band (does distance explain delays?)
SELECT
    distance_band,
    COUNT(*) AS n_orders,
    ROUND(AVG(avg_distance_km)::numeric, 0) AS avg_distance_km,
    ROUND(AVG(lead_time_days)::numeric, 2) AS avg_lead_time_days,
    ROUND(AVG(total_freight_value)::numeric, 2) AS avg_freight_value,
    ROUND(100.0 * SUM(CASE WHEN otd_status = 'Late' THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN otd_status IN ('On Time','Late') THEN 1 ELSE 0 END), 0), 2)
        AS late_pct
FROM gold.fact_delivery
WHERE order_status = 'delivered'
GROUP BY distance_band
ORDER BY avg_distance_km NULLS LAST;

-- State-level performance: worst customer experience by state
SELECT
    dc.state,
    COUNT(*) AS n_orders,
    ROUND(AVG(fd.lead_time_days)::numeric, 2) AS avg_lead_time_days,
    ROUND(100.0 * SUM(CASE WHEN fd.otd_status = 'Late' THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN fd.otd_status IN ('On Time','Late') THEN 1 ELSE 0 END), 0), 2)
        AS late_pct,
    ROUND(AVG(fd.review_score)::numeric, 2) AS avg_review_score
FROM gold.fact_delivery fd
JOIN gold.dim_customer dc ON dc.customer_key = fd.customer_key
WHERE fd.order_status = 'delivered'
GROUP BY dc.state
HAVING COUNT(*) >= 30
ORDER BY late_pct DESC;

-- Scatter-plot source data: distance vs delivery time vs freight vs OTD
-- (X = distance, Y = lead time, size = freight, colour = otd_status)
SELECT
    fd.order_id,
    fd.avg_distance_km AS distance_km,
    fd.lead_time_days,
    fd.total_freight_value AS freight_value,
    fd.otd_status
FROM gold.fact_delivery fd
WHERE fd.order_status = 'delivered' AND fd.avg_distance_km IS NOT NULL;
