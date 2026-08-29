-- DASHBOARD 2 — ORDER FULFILMENT
-- Lead-time decomposition: Purchase -> Payment -> Seller Fulfilment -> Transit -> Delivered

-- Average time spent in each stage, in days, across valid delivered orders.
SELECT
    ROUND(AVG(payment_time_hours) / 24.0, 2) AS avg_payment_days,
    ROUND(AVG(fulfilment_time_hours) / 24.0, 2) AS avg_fulfilment_days,
    ROUND(AVG(transit_time_hours) / 24.0, 2) AS avg_transit_days,
    ROUND(AVG(lead_time_days), 2) AS avg_total_lead_days
FROM gold.fact_delivery
WHERE is_valid_for_lead_time_analysis AND order_status = 'delivered';

-- Same decomposition trended by month, to see whether the bottleneck stage
-- is improving, worsening, or stable.
SELECT
    d.year_month,
    ROUND(AVG(fd.payment_time_hours) / 24.0, 2) AS avg_payment_days,
    ROUND(AVG(fd.fulfilment_time_hours) / 24.0, 2) AS avg_fulfilment_days,
    ROUND(AVG(fd.transit_time_hours) / 24.0, 2) AS avg_transit_days,
    ROUND(AVG(fd.lead_time_days), 2) AS avg_total_lead_days
FROM gold.fact_delivery fd
JOIN gold.dim_date d ON d.date_id = fd.purchase_date_id
WHERE fd.is_valid_for_lead_time_analysis AND fd.order_status = 'delivered'
GROUP BY d.year_month
ORDER BY d.year_month;

-- Late-order drill-down: for late orders only, which stage looks abnormal
-- relative to the on-time population (root-cause signal).
SELECT
    otd_status,
    COUNT(*) AS n_orders,
    ROUND(AVG(payment_time_hours) / 24.0, 2) AS avg_payment_days,
    ROUND(AVG(fulfilment_time_hours) / 24.0, 2) AS avg_fulfilment_days,
    ROUND(AVG(transit_time_hours) / 24.0, 2) AS avg_transit_days
FROM gold.fact_delivery
WHERE is_valid_for_lead_time_analysis AND order_status = 'delivered'
GROUP BY otd_status;
