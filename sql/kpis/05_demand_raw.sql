-- DASHBOARD 5 - DEMAND & RISK INTELLIGENCE (raw inputs)
-- Weekly units sold per category on a COMPLETE category x week grid: weeks
-- with no sales are present as 0. (v1 only returned weeks with sales, which
-- understated volatility for sparse categories.)
-- Only full Monday-Sunday weeks inside the analysis window are used, so the
-- sparse edges of the dataset cannot show up as demand "drops".
WITH weeks AS (
    SELECT DISTINCT week_start
    FROM gold.dim_date
    WHERE is_in_analysis_window
      AND week_start >= (SELECT start_date FROM gold.analysis_window)
      AND week_start + INTERVAL 6 DAY <= (SELECT end_date FROM gold.analysis_window)
),
categories AS (
    SELECT DISTINCT category_en FROM gold.dim_product
),
sales AS (
    SELECT
        dp.category_en,
        d.week_start,
        COUNT(*) AS n_items_sold,
        SUM(foi.price) AS revenue
    FROM gold.fact_order_item foi
    JOIN gold.dim_product dp ON dp.product_key = foi.product_key
    JOIN gold.dim_date d ON d.date_id = foi.purchase_date_id
    WHERE foi.is_revenue_status
    GROUP BY dp.category_en, d.week_start
)
SELECT
    c.category_en,
    w.week_start,
    COALESCE(s.n_items_sold, 0) AS n_items_sold,
    ROUND(COALESCE(s.revenue, 0), 2) AS revenue
FROM categories c
CROSS JOIN weeks w
LEFT JOIN sales s ON s.category_en = c.category_en AND s.week_start = w.week_start
ORDER BY c.category_en, w.week_start;
