-- DASHBOARD 3 - LOGISTICS INTELLIGENCE
-- Population: delivered orders. Late = delivered after the promised DATE.

-- Late rate and lead time by distance band.
SELECT
    distance_band,
    COUNT(*) AS n_orders,
    ROUND(AVG(avg_distance_km), 0) AS avg_distance_km,
    ROUND(AVG(lead_time_days), 2) AS avg_lead_time_days,
    ROUND(AVG(freight_value), 2) AS avg_freight_value,
    SUM((otd_status = 'Late')::INT) AS n_late,
    ROUND(100.0 * AVG((otd_status = 'Late')::INT), 2) AS late_pct
FROM gold.fact_order
WHERE is_delivered
GROUP BY distance_band
ORDER BY avg_distance_km NULLS LAST;

-- Customer-state performance (states with >= 30 delivered orders).
SELECT
    customer_state AS state,
    COUNT(*) AS n_orders,
    ROUND(AVG(lead_time_days), 2) AS avg_lead_time_days,
    SUM((otd_status = 'Late')::INT) AS n_late,
    ROUND(100.0 * AVG((otd_status = 'Late')::INT), 2) AS late_pct,
    ROUND(AVG(review_score), 2) AS avg_review_score
FROM gold.fact_order
WHERE is_delivered
GROUP BY customer_state
HAVING COUNT(*) >= 30
ORDER BY late_pct DESC;

-- Scatter source: distance vs lead time vs freight vs on-time status.
SELECT
    order_id,
    avg_distance_km AS distance_km,
    lead_time_days,
    freight_value,
    review_score,
    otd_status
FROM gold.fact_order
WHERE is_delivered AND avg_distance_km IS NOT NULL AND lead_time_days IS NOT NULL;
