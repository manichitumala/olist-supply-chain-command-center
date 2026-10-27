-- GOLD LAYER (DuckDB)
-- Star schema built from silver. Expects gold.analysis_window to exist
-- (created by src/transformation/build_gold.py from src/config.py).
--
-- Fact tables and their grain:
--   fact_order_item   one product unit within one order
--   fact_seller_order one seller within one order   (seller-level metrics)
--   fact_order        one order, ALL 99,441 orders  (order-level KPIs)
--
-- v2 corrections vs the PostgreSQL version:
--   * On-time is judged on calendar DATES. estimated_ts is always 00:00, so a
--     timestamp comparison marked every order delivered ON its due date as
--     late (1,292 orders, OTD 91.89% -> 93.23%).
--   * Seller- and category-level rates are computed at seller-order /
--     category-order grain. v1 aggregated over item rows, so an order with 3
--     items counted 3 times in a seller's on-time rate.
--   * fact_order keeps orders that have no items (mostly unavailable /
--     cancelled), so cancellation rate has the right denominator.

CREATE SCHEMA IF NOT EXISTS gold;

-- ============================================================
-- DIM_DATE
-- ============================================================
CREATE OR REPLACE TABLE gold.dim_date AS
WITH bounds AS (
    SELECT MIN(purchase_ts)::DATE AS min_d, (MAX(purchase_ts) + INTERVAL 60 DAY)::DATE AS max_d
    FROM silver.orders
),
d AS (
    SELECT CAST(UNNEST(generate_series(min_d::TIMESTAMP, max_d::TIMESTAMP, INTERVAL 1 DAY)) AS DATE) AS full_date
    FROM bounds
)
SELECT
    CAST(strftime(full_date, '%Y%m%d') AS INTEGER) AS date_id,
    full_date,
    year(full_date) AS year,
    month(full_date) AS month,
    monthname(full_date) AS month_name,
    quarter(full_date) AS quarter,
    strftime(full_date, '%Y-%m') AS year_month,
    CAST(date_trunc('week', full_date) AS DATE) AS week_start,
    dayname(full_date) AS day_of_week,
    isodow(full_date) IN (6, 7) AS is_weekend,
    full_date BETWEEN w.start_date AND w.end_date AS is_in_analysis_window
FROM d, gold.analysis_window w;

-- ============================================================
-- DIM_GEOGRAPHY: one row per zip prefix seen on a customer or seller,
-- with a state-centroid fallback where no geolocation sample exists.
-- ============================================================
CREATE OR REPLACE TABLE gold.dim_geography AS
WITH state_centroid AS (
    SELECT state, AVG(lat) AS state_lat, AVG(lon) AS state_lon
    FROM silver.geolocation_zip GROUP BY state
),
all_zips AS (
    SELECT DISTINCT ON (zip_prefix) zip_prefix, state
    FROM (SELECT zip_prefix, state FROM silver.customers
          UNION ALL
          SELECT zip_prefix, state FROM silver.sellers)
    ORDER BY zip_prefix, state
)
SELECT
    z.zip_prefix,
    COALESCE(g.state, z.state) AS state,
    g.city,
    COALESCE(g.lat, sc.state_lat) AS lat,
    COALESCE(g.lon, sc.state_lon) AS lon,
    (g.lat IS NULL) AS is_state_centroid_fallback,
    CASE
        WHEN COALESCE(g.state, z.state) IN ('AC','AP','AM','PA','RO','RR','TO') THEN 'North'
        WHEN COALESCE(g.state, z.state) IN ('AL','BA','CE','MA','PB','PE','PI','RN','SE') THEN 'Northeast'
        WHEN COALESCE(g.state, z.state) IN ('DF','GO','MT','MS') THEN 'Central-West'
        WHEN COALESCE(g.state, z.state) IN ('ES','MG','RJ','SP') THEN 'Southeast'
        WHEN COALESCE(g.state, z.state) IN ('PR','RS','SC') THEN 'South'
        ELSE 'Unknown'
    END AS region
FROM all_zips z
LEFT JOIN silver.geolocation_zip g ON g.zip_prefix = z.zip_prefix
LEFT JOIN state_centroid sc ON sc.state = COALESCE(g.state, z.state);

-- ============================================================
-- DIMENSIONS: customer / seller / product
-- ============================================================
CREATE OR REPLACE TABLE gold.dim_customer AS
SELECT
    c.customer_id AS customer_key,
    c.customer_unique_id,
    c.zip_prefix,
    c.city,
    c.state,
    g.region,
    g.lat,
    g.lon
FROM silver.customers c
LEFT JOIN gold.dim_geography g ON g.zip_prefix = c.zip_prefix;

CREATE OR REPLACE TABLE gold.dim_seller AS
SELECT
    s.seller_id AS seller_key,
    s.zip_prefix,
    s.city,
    s.state,
    g.region,
    g.lat,
    g.lon
FROM silver.sellers s
LEFT JOIN gold.dim_geography g ON g.zip_prefix = s.zip_prefix;

CREATE OR REPLACE TABLE gold.dim_product AS
SELECT
    product_id AS product_key,
    category_en,
    category_pt,
    is_untranslated_category,
    weight_g,
    length_cm,
    height_cm,
    width_cm,
    volume_cm3,
    photos_qty
FROM silver.products;

-- ============================================================
-- FACT_ORDER_ITEM (grain: order_id + order_item_id)
-- Haversine distance between seller and customer zip centroids.
-- ============================================================
CREATE OR REPLACE TABLE gold.fact_order_item AS
SELECT
    oi.order_id,
    oi.order_item_id,
    o.customer_id AS customer_key,
    oi.seller_id AS seller_key,
    oi.product_id AS product_key,
    CAST(strftime(o.purchase_ts, '%Y%m%d') AS INTEGER) AS purchase_date_id,
    o.order_status,
    o.order_status NOT IN ('canceled', 'unavailable') AS is_revenue_status,
    oi.shipping_limit_ts,
    oi.price,
    oi.freight_value,
    ROUND(6371 * ACOS(LEAST(1.0, GREATEST(-1.0,
        COS(RADIANS(cg.lat)) * COS(RADIANS(sg.lat)) * COS(RADIANS(sg.lon) - RADIANS(cg.lon))
        + SIN(RADIANS(cg.lat)) * SIN(RADIANS(sg.lat))
    ))), 1) AS distance_km
FROM silver.order_items oi
JOIN silver.orders o ON o.order_id = oi.order_id
LEFT JOIN silver.customers c ON c.customer_id = o.customer_id
LEFT JOIN silver.sellers s ON s.seller_id = oi.seller_id
LEFT JOIN gold.dim_geography cg ON cg.zip_prefix = c.zip_prefix
LEFT JOIN gold.dim_geography sg ON sg.zip_prefix = s.zip_prefix;

-- ============================================================
-- FACT_ORDER (grain: order_id, every order including those with no items)
-- ============================================================
CREATE OR REPLACE TABLE gold.fact_order AS
WITH items AS (
    SELECT
        order_id,
        COUNT(*) AS n_items,
        COUNT(DISTINCT seller_key) AS n_distinct_sellers,
        SUM(price) AS items_value,
        SUM(freight_value) AS freight_value,
        AVG(distance_km) AS avg_distance_km
    FROM gold.fact_order_item
    GROUP BY order_id
),
payments AS (
    SELECT order_id, SUM(payment_value) AS payment_value
    FROM silver.order_payments GROUP BY order_id
),
base AS (
    SELECT
        o.*,
        (o.order_status = 'delivered' AND o.delivered_ts IS NOT NULL) AS is_delivered,
        COALESCE(i.n_items, 0) AS n_items,
        COALESCE(i.n_distinct_sellers, 0) AS n_distinct_sellers,
        i.items_value,
        i.freight_value,
        p.payment_value,
        i.avg_distance_km
    FROM silver.orders o
    LEFT JOIN items i ON i.order_id = o.order_id
    LEFT JOIN payments p ON p.order_id = o.order_id
)
SELECT
    b.order_id,
    b.customer_id AS customer_key,
    c.customer_unique_id,
    c.state AS customer_state,
    c.region AS customer_region,
    CAST(strftime(b.purchase_ts, '%Y%m%d') AS INTEGER) AS purchase_date_id,
    CAST(b.purchase_ts AS DATE) BETWEEN w.start_date AND w.end_date AS is_in_analysis_window,
    b.order_status,
    b.purchase_ts,
    b.approved_ts,
    b.carrier_ts,
    b.delivered_ts,
    b.estimated_ts,
    b.is_valid_for_lead_time_analysis,

    (b.n_items > 0) AS has_items,
    b.n_items,
    b.n_distinct_sellers,
    (b.n_distinct_sellers > 1) AS is_multi_seller_order,
    CASE
        WHEN b.n_distinct_sellers = 0 THEN 'none'
        WHEN b.n_distinct_sellers = 1 THEN '1'
        WHEN b.n_distinct_sellers = 2 THEN '2'
        ELSE '3+'
    END AS sellers_per_order_band,
    b.items_value,
    b.freight_value,
    b.payment_value,

    -- Revenue (GMV) counts only orders that were not cancelled/unavailable.
    (b.n_items > 0 AND b.order_status NOT IN ('canceled', 'unavailable')) AS is_revenue_order,
    (b.order_status = 'canceled') AS is_canceled,
    b.is_delivered,

    -- Lead-time decomposition (hours / days). NULL when inputs are missing
    -- or the sequence was flagged invalid in silver.
    CASE WHEN b.is_valid_for_lead_time_analysis AND b.approved_ts IS NOT NULL
         THEN (epoch(b.approved_ts) - epoch(b.purchase_ts)) / 3600.0 END AS payment_time_hours,
    CASE WHEN b.is_valid_for_lead_time_analysis AND b.carrier_ts IS NOT NULL AND b.approved_ts IS NOT NULL
         THEN (epoch(b.carrier_ts) - epoch(b.approved_ts)) / 3600.0 END AS fulfilment_time_hours,
    CASE WHEN b.is_valid_for_lead_time_analysis AND b.delivered_ts IS NOT NULL AND b.carrier_ts IS NOT NULL
         THEN (epoch(b.delivered_ts) - epoch(b.carrier_ts)) / 3600.0 END AS transit_time_hours,
    CASE WHEN b.is_valid_for_lead_time_analysis AND b.is_delivered
         THEN (epoch(b.delivered_ts) - epoch(b.purchase_ts)) / 86400.0 END AS lead_time_days,

    -- Delivery promise, judged on calendar dates (see header note).
    CASE
        WHEN NOT b.is_delivered THEN 'Not Delivered'
        WHEN CAST(b.delivered_ts AS DATE) <= CAST(b.estimated_ts AS DATE) THEN 'On Time'
        ELSE 'Late'
    END AS otd_status,
    CASE WHEN b.is_delivered
         THEN date_diff('day', CAST(b.estimated_ts AS DATE), CAST(b.delivered_ts AS DATE)) END
         AS days_late,   -- positive = late, <= 0 = on time / early
    date_diff('day', CAST(b.purchase_ts AS DATE), CAST(b.estimated_ts AS DATE)) AS promised_days,

    r.review_score,
    b.avg_distance_km,
    CASE
        WHEN b.avg_distance_km IS NULL THEN 'Unknown'
        WHEN b.avg_distance_km < 100 THEN '0-100 km'
        WHEN b.avg_distance_km < 300 THEN '100-300 km'
        WHEN b.avg_distance_km < 500 THEN '300-500 km'
        WHEN b.avg_distance_km < 1000 THEN '500-1000 km'
        ELSE '1000+ km'
    END AS distance_band
FROM base b
CROSS JOIN gold.analysis_window w
LEFT JOIN gold.dim_customer c ON c.customer_key = b.customer_id
LEFT JOIN silver.order_reviews r ON r.order_id = b.order_id;

-- ============================================================
-- FACT_SELLER_ORDER (grain: order_id + seller_key)
-- The unit for every seller-level metric. Delivery outcome, fulfilment time
-- and review are captured once per ORDER by Olist, so in a multi-seller
-- order (~1.3% of orders) each seller inherits the order's values. The
-- shipping_limit_ts, however, is set per seller, so missed_shipping_limit is
-- a genuinely seller-attributable signal.
-- ============================================================
CREATE OR REPLACE TABLE gold.fact_seller_order AS
WITH seller_items AS (
    SELECT
        order_id,
        seller_key,
        COUNT(*) AS n_items,
        SUM(price) AS item_revenue,
        SUM(freight_value) AS freight_value,
        AVG(distance_km) AS distance_km,
        MAX(shipping_limit_ts) AS shipping_limit_ts
    FROM gold.fact_order_item
    GROUP BY order_id, seller_key
)
SELECT
    si.order_id,
    si.seller_key,
    fo.customer_key,
    fo.purchase_ts,
    fo.purchase_date_id,
    fo.is_in_analysis_window,
    fo.order_status,
    fo.is_revenue_order,
    fo.is_canceled,
    fo.is_delivered,
    fo.is_multi_seller_order,
    si.n_items,
    si.item_revenue,
    si.freight_value,
    si.distance_km,
    si.shipping_limit_ts,
    fo.carrier_ts,
    CASE WHEN fo.carrier_ts IS NOT NULL AND fo.is_valid_for_lead_time_analysis
         THEN fo.carrier_ts > si.shipping_limit_ts END AS missed_shipping_limit,
    fo.fulfilment_time_hours,
    fo.otd_status,
    fo.days_late,
    fo.review_score
FROM seller_items si
JOIN gold.fact_order fo ON fo.order_id = si.order_id;
