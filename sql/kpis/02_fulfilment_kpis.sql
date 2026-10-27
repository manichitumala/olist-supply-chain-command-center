-- DASHBOARD 2 - ORDER FULFILMENT
-- Lead-time decomposition: Purchase -> Payment -> Seller Fulfilment -> Transit -> Delivered
-- Population: delivered orders whose timestamps passed the silver sequence checks.

-- Average days in each stage.
SELECT
    COUNT(*) AS n_orders,
    ROUND(AVG(payment_time_hours) / 24.0, 2) AS avg_payment_days,
    ROUND(AVG(fulfilment_time_hours) / 24.0, 2) AS avg_fulfilment_days,
    ROUND(AVG(transit_time_hours) / 24.0, 2) AS avg_transit_days,
    ROUND(AVG(lead_time_days), 2) AS avg_total_lead_days
FROM gold.fact_order
WHERE is_valid_for_lead_time_analysis AND is_delivered;

-- Same decomposition by month (analysis window only).
SELECT
    strftime(purchase_ts, '%Y-%m') AS year_month,
    ROUND(AVG(payment_time_hours) / 24.0, 2) AS avg_payment_days,
    ROUND(AVG(fulfilment_time_hours) / 24.0, 2) AS avg_fulfilment_days,
    ROUND(AVG(transit_time_hours) / 24.0, 2) AS avg_transit_days,
    ROUND(AVG(lead_time_days), 2) AS avg_total_lead_days
FROM gold.fact_order
WHERE is_valid_for_lead_time_analysis AND is_delivered AND is_in_analysis_window
GROUP BY year_month
ORDER BY year_month;

-- On-time vs late: which stage is abnormal for late orders.
SELECT
    otd_status,
    COUNT(*) AS n_orders,
    ROUND(AVG(payment_time_hours) / 24.0, 2) AS avg_payment_days,
    ROUND(AVG(fulfilment_time_hours) / 24.0, 2) AS avg_fulfilment_days,
    ROUND(AVG(transit_time_hours) / 24.0, 2) AS avg_transit_days,
    ROUND(MEDIAN(transit_time_hours) / 24.0, 2) AS median_transit_days
FROM gold.fact_order
WHERE is_valid_for_lead_time_analysis AND is_delivered
GROUP BY otd_status
ORDER BY otd_status DESC;
