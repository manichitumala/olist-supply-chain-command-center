-- GOLD LAYER
-- Analytics star schema built from silver via feature engineering.
-- Grain of fact_order_item = one product item within one order (deliberately
-- NOT order-level) so seller-level operational problems inside multi-seller
-- orders stay visible instead of being averaged away.
-- fact_delivery is order-grain: delivery timestamps in Olist are captured
-- once per order, not once per item/shipment.

CREATE SCHEMA IF NOT EXISTS gold;

DROP TABLE IF EXISTS gold.fact_delivery;
DROP TABLE IF EXISTS gold.fact_order_item;
DROP TABLE IF EXISTS gold.dim_product;
DROP TABLE IF EXISTS gold.dim_seller;
DROP TABLE IF EXISTS gold.dim_customer;
DROP TABLE IF EXISTS gold.dim_geography;
DROP TABLE IF EXISTS gold.dim_date;

-- ============================================================
-- DIM_DATE
-- ============================================================
CREATE TABLE gold.dim_date AS
WITH bounds AS (
    SELECT MIN(purchase_ts)::date AS min_d, (MAX(purchase_ts) + INTERVAL '30 days')::date AS max_d
    FROM silver.orders
),
d AS (
    SELECT generate_series(min_d, max_d, INTERVAL '1 day')::date AS full_date
    FROM bounds
)
SELECT
    (TO_CHAR(full_date, 'YYYYMMDD'))::int AS date_id,
    full_date,
    EXTRACT(YEAR FROM full_date)::int AS year,
    EXTRACT(MONTH FROM full_date)::int AS month,
    TO_CHAR(full_date, 'Month') AS month_name,
    EXTRACT(QUARTER FROM full_date)::int AS quarter,
    TO_CHAR(full_date, 'YYYY-MM') AS year_month,
    TRIM(TO_CHAR(full_date, 'Day')) AS day_of_week,
    EXTRACT(ISODOW FROM full_date) IN (6, 7) AS is_weekend
FROM d;

ALTER TABLE gold.dim_date ADD PRIMARY KEY (date_id);

-- ============================================================
-- DIM_GEOGRAPHY (one row per zip prefix, plus a state-centroid
-- fallback for zip prefixes with no geolocation sample at all)
-- ============================================================
CREATE TABLE gold.dim_geography AS
WITH state_centroid AS (
    SELECT state, AVG(lat) AS state_lat, AVG(lon) AS state_lon
    FROM silver.geolocation_zip
    GROUP BY state
),
all_zips AS (
    SELECT DISTINCT ON (zip_prefix) zip_prefix, state
    FROM (
        SELECT zip_prefix, state FROM silver.customers
        UNION ALL
        SELECT zip_prefix, state FROM silver.sellers
    ) t
    ORDER BY zip_prefix
)
SELECT
    z.zip_prefix,
    COALESCE(g.state, z.state) AS state,
    g.city,
    COALESCE(g.lat, sc.state_lat) AS lat,
    COALESCE(g.lon, sc.state_lon) AS lon,
    (g.lat IS NULL) AS is_state_centroid_fallback,
    CASE COALESCE(g.state, z.state)
        WHEN 'AC' THEN 'North'        WHEN 'AP' THEN 'North'
        WHEN 'AM' THEN 'North'        WHEN 'PA' THEN 'North'
        WHEN 'RO' THEN 'North'        WHEN 'RR' THEN 'North'
        WHEN 'TO' THEN 'North'
        WHEN 'AL' THEN 'Northeast'    WHEN 'BA' THEN 'Northeast'
        WHEN 'CE' THEN 'Northeast'    WHEN 'MA' THEN 'Northeast'
        WHEN 'PB' THEN 'Northeast'    WHEN 'PE' THEN 'Northeast'
        WHEN 'PI' THEN 'Northeast'    WHEN 'RN' THEN 'Northeast'
        WHEN 'SE' THEN 'Northeast'
        WHEN 'DF' THEN 'Central-West' WHEN 'GO' THEN 'Central-West'
        WHEN 'MT' THEN 'Central-West' WHEN 'MS' THEN 'Central-West'
        WHEN 'ES' THEN 'Southeast'    WHEN 'MG' THEN 'Southeast'
        WHEN 'RJ' THEN 'Southeast'    WHEN 'SP' THEN 'Southeast'
        WHEN 'PR' THEN 'South'        WHEN 'RS' THEN 'South'
        WHEN 'SC' THEN 'South'
        ELSE 'Unknown'
    END AS region
FROM all_zips z
LEFT JOIN silver.geolocation_zip g ON g.zip_prefix = z.zip_prefix
LEFT JOIN state_centroid sc ON sc.state = COALESCE(g.state, z.state);

ALTER TABLE gold.dim_geography ADD PRIMARY KEY (zip_prefix);

-- ============================================================
-- DIM_CUSTOMER / DIM_SELLER / DIM_PRODUCT
-- ============================================================
CREATE TABLE gold.dim_customer AS
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

ALTER TABLE gold.dim_customer ADD PRIMARY KEY (customer_key);

CREATE TABLE gold.dim_seller AS
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

ALTER TABLE gold.dim_seller ADD PRIMARY KEY (seller_key);

CREATE TABLE gold.dim_product AS
SELECT
    product_id AS product_key,
    category_en,
    category_pt,
    weight_g,
    length_cm,
    height_cm,
    width_cm,
    volume_cm3,
    photos_qty
FROM silver.products;

ALTER TABLE gold.dim_product ADD PRIMARY KEY (product_key);

-- ============================================================
-- Order-level complexity: items and distinct sellers per order.
-- This is the multi-seller-order metric the root-cause analysis needs.
-- ============================================================
CREATE TEMP TABLE order_complexity AS
SELECT
    order_id,
    COUNT(*) AS n_items,
    COUNT(DISTINCT seller_id) AS n_distinct_sellers,
    SUM(price) AS total_price,
    SUM(freight_value) AS total_freight_value
FROM silver.order_items
GROUP BY order_id;

-- ============================================================
-- FACT_ORDER_ITEM  (grain: order_id + order_item_id)
-- Haversine distance is computed here, per seller-customer item pair.
-- ============================================================
CREATE TABLE gold.fact_order_item AS
SELECT
    oi.order_id,
    oi.order_item_id,
    o.customer_id AS customer_key,
    oi.seller_id AS seller_key,
    oi.product_id AS product_key,
    (TO_CHAR(o.purchase_ts, 'YYYYMMDD'))::int AS purchase_date_id,
    o.order_status,
    oi.price,
    oi.freight_value,
    oc.n_items AS n_items_in_order,
    oc.n_distinct_sellers AS n_distinct_sellers_in_order,
    (oc.n_distinct_sellers > 1) AS is_multi_seller_order,
    CASE
        WHEN oc.n_distinct_sellers = 1 THEN '1'
        WHEN oc.n_distinct_sellers = 2 THEN '2'
        ELSE '3+'
    END AS sellers_per_order_band,
    -- Haversine distance in km between seller and customer zip centroids
    ROUND((6371 * ACOS(
        LEAST(1.0, GREATEST(-1.0,
            COS(RADIANS(cg.lat)) * COS(RADIANS(sg.lat)) * COS(RADIANS(sg.lon) - RADIANS(cg.lon))
            + SIN(RADIANS(cg.lat)) * SIN(RADIANS(sg.lat))
        ))
    ))::numeric, 1) AS distance_km
FROM silver.order_items oi
JOIN silver.orders o ON o.order_id = oi.order_id
JOIN order_complexity oc ON oc.order_id = oi.order_id
LEFT JOIN gold.dim_customer dc ON dc.customer_key = o.customer_id
LEFT JOIN gold.dim_seller ds ON ds.seller_key = oi.seller_id
LEFT JOIN gold.dim_geography cg ON cg.zip_prefix = dc.zip_prefix
LEFT JOIN gold.dim_geography sg ON sg.zip_prefix = ds.zip_prefix;

ALTER TABLE gold.fact_order_item ADD PRIMARY KEY (order_id, order_item_id);
CREATE INDEX idx_foi_seller ON gold.fact_order_item(seller_key);
CREATE INDEX idx_foi_product ON gold.fact_order_item(product_key);
CREATE INDEX idx_foi_date ON gold.fact_order_item(purchase_date_id);

-- ============================================================
-- FACT_DELIVERY (grain: order_id)
-- Lead-time decomposition + SLA classification + distance rollup.
-- Scope note: the JOIN to order_complexity is intentionally an INNER JOIN,
-- so this table only covers the 98,666 of 99,441 orders that have at least
-- one order_item. The other 775 (603 'unavailable', 164 'canceled', plus a
-- handful of 'created'/'invoiced'/'shipped') never had a fulfillable item
-- attached and have nothing to compute a lead time or distance from -- they
-- are genuinely out of scope for a delivery/fulfilment fact table, not a
-- silent data-loss bug.
-- ============================================================
CREATE TABLE gold.fact_delivery AS
SELECT
    o.order_id,
    o.customer_id AS customer_key,
    (TO_CHAR(o.purchase_ts, 'YYYYMMDD'))::int AS purchase_date_id,
    o.order_status,
    o.purchase_ts,
    o.approved_ts,
    o.carrier_ts,
    o.delivered_ts,
    o.estimated_ts,
    o.is_valid_for_lead_time_analysis,

    -- lead-time decomposition, in hours (NULL when the stage's inputs
    -- are missing or the sequence was flagged invalid upstream)
    CASE WHEN o.is_valid_for_lead_time_analysis AND o.approved_ts IS NOT NULL
         THEN EXTRACT(EPOCH FROM (o.approved_ts - o.purchase_ts)) / 3600.0 END
         AS payment_time_hours,
    CASE WHEN o.is_valid_for_lead_time_analysis AND o.carrier_ts IS NOT NULL AND o.approved_ts IS NOT NULL
         THEN EXTRACT(EPOCH FROM (o.carrier_ts - o.approved_ts)) / 3600.0 END
         AS fulfilment_time_hours,
    CASE WHEN o.is_valid_for_lead_time_analysis AND o.delivered_ts IS NOT NULL AND o.carrier_ts IS NOT NULL
         THEN EXTRACT(EPOCH FROM (o.delivered_ts - o.carrier_ts)) / 3600.0 END
         AS transit_time_hours,
    CASE WHEN o.is_valid_for_lead_time_analysis AND o.delivered_ts IS NOT NULL
         THEN EXTRACT(EPOCH FROM (o.delivered_ts - o.purchase_ts)) / 86400.0 END
         AS lead_time_days,

    -- SLA classification vs the estimated delivery date the customer saw
    CASE
        WHEN o.delivered_ts IS NULL THEN 'Not Delivered'
        WHEN o.delivered_ts <= o.estimated_ts THEN 'On Time'
        ELSE 'Late'
    END AS otd_status,
    CASE WHEN o.delivered_ts IS NOT NULL
         THEN EXTRACT(EPOCH FROM (o.delivered_ts - o.estimated_ts)) / 86400.0 END
         AS days_vs_estimate,

    r.review_score,
    oc.n_items,
    oc.n_distinct_sellers,
    (oc.n_distinct_sellers > 1) AS is_multi_seller_order,
    CASE
        WHEN oc.n_distinct_sellers = 1 THEN '1'
        WHEN oc.n_distinct_sellers = 2 THEN '2'
        ELSE '3+'
    END AS sellers_per_order_band,
    oc.total_price,
    oc.total_freight_value,
    p.total_payment_value,

    dist.avg_distance_km,
    CASE
        WHEN dist.avg_distance_km IS NULL THEN 'Unknown'
        WHEN dist.avg_distance_km < 100 THEN '0-100 km'
        WHEN dist.avg_distance_km < 300 THEN '100-300 km'
        WHEN dist.avg_distance_km < 500 THEN '300-500 km'
        WHEN dist.avg_distance_km < 1000 THEN '500-1000 km'
        ELSE '1000+ km'
    END AS distance_band
FROM silver.orders o
JOIN order_complexity oc ON oc.order_id = o.order_id
LEFT JOIN silver.order_reviews r ON r.order_id = o.order_id
LEFT JOIN (
    SELECT order_id, SUM(payment_value) AS total_payment_value
    FROM silver.order_payments
    GROUP BY order_id
) p ON p.order_id = o.order_id
LEFT JOIN (
    SELECT order_id, AVG(distance_km) AS avg_distance_km
    FROM gold.fact_order_item
    GROUP BY order_id
) dist ON dist.order_id = o.order_id;

ALTER TABLE gold.fact_delivery ADD PRIMARY KEY (order_id);
CREATE INDEX idx_fd_customer ON gold.fact_delivery(customer_key);
CREATE INDEX idx_fd_date ON gold.fact_delivery(purchase_date_id);
CREATE INDEX idx_fd_otd ON gold.fact_delivery(otd_status);
