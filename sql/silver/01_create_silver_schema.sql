-- SILVER LAYER
-- Cleaned, typed, deduplicated data built from bronze via SQL transformations.
-- Cleaning rules here are a direct response to the bronze data-quality audit
-- (see reports/data_quality_report.md):
--   * 610 products have no category            -> coalesced to 'unknown'
--   * 1,359 orders have carrier date < approved -> flagged, not silently fixed
--   * 23 orders have delivered < carrier date   -> flagged, not silently fixed
--   * 8 'delivered' orders have no delivered ts -> flagged as a data bug
--   * 814 duplicate review_ids / 551 orders with >1 review -> deduped, latest kept
--   * 157 customer zips / 7 seller zips have no geolocation row -> left NULL,
--     handled downstream with a state-centroid fallback in the gold layer

CREATE SCHEMA IF NOT EXISTS silver;

DROP TABLE IF EXISTS silver.order_reviews;
DROP TABLE IF EXISTS silver.order_payments;
DROP TABLE IF EXISTS silver.order_items;
DROP TABLE IF EXISTS silver.orders;
DROP TABLE IF EXISTS silver.products;
DROP TABLE IF EXISTS silver.sellers;
DROP TABLE IF EXISTS silver.customers;
DROP TABLE IF EXISTS silver.geolocation_zip;

-- ============================================================
-- Geolocation aggregated to one row per zip prefix.
-- Raw geolocation has many noisy lat/lon samples per prefix (crowd-sourced);
-- we filter to Brazil's bounding box to drop obvious geocoding errors, then
-- average. City/state are taken as the most frequent value per prefix.
-- ============================================================
CREATE TABLE silver.geolocation_zip AS
WITH bounded AS (
    SELECT
        geolocation_zip_code_prefix::int AS zip_prefix,
        geolocation_lat::double precision AS lat,
        geolocation_lng::double precision AS lon,
        geolocation_city AS city,
        geolocation_state AS state
    FROM bronze.geolocation
    WHERE geolocation_lat::double precision BETWEEN -33.75 AND 5.27
      AND geolocation_lng::double precision BETWEEN -73.99 AND -34.79
),
city_mode AS (
    SELECT DISTINCT ON (zip_prefix)
        zip_prefix, city, state
    FROM (
        SELECT zip_prefix, city, state, COUNT(*) AS n
        FROM bounded
        GROUP BY zip_prefix, city, state
    ) t
    ORDER BY zip_prefix, n DESC
)
SELECT
    b.zip_prefix,
    AVG(b.lat) AS lat,
    AVG(b.lon) AS lon,
    cm.city,
    cm.state
FROM bounded b
JOIN city_mode cm ON cm.zip_prefix = b.zip_prefix
GROUP BY b.zip_prefix, cm.city, cm.state;

ALTER TABLE silver.geolocation_zip ADD PRIMARY KEY (zip_prefix);

-- ============================================================
-- Customers
-- ============================================================
CREATE TABLE silver.customers AS
SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix::int AS zip_prefix,
    customer_city AS city,
    customer_state AS state
FROM bronze.customers;

ALTER TABLE silver.customers ADD PRIMARY KEY (customer_id);

-- ============================================================
-- Sellers
-- ============================================================
CREATE TABLE silver.sellers AS
SELECT
    seller_id,
    seller_zip_code_prefix::int AS zip_prefix,
    seller_city AS city,
    seller_state AS state
FROM bronze.sellers;

ALTER TABLE silver.sellers ADD PRIMARY KEY (seller_id);

-- ============================================================
-- Products (category translated to English, missing -> 'unknown')
-- ============================================================
CREATE TABLE silver.products AS
SELECT
    p.product_id,
    COALESCE(t.product_category_name_english, 'unknown') AS category_en,
    COALESCE(p.product_category_name, 'unknown') AS category_pt,
    NULLIF(p.product_name_lenght, '')::int AS name_length,
    NULLIF(p.product_description_lenght, '')::int AS description_length,
    COALESCE(NULLIF(p.product_photos_qty, '')::int, 0) AS photos_qty,
    NULLIF(p.product_weight_g, '')::numeric AS weight_g,
    NULLIF(p.product_length_cm, '')::numeric AS length_cm,
    NULLIF(p.product_height_cm, '')::numeric AS height_cm,
    NULLIF(p.product_width_cm, '')::numeric AS width_cm,
    (NULLIF(p.product_length_cm, '')::numeric
        * NULLIF(p.product_height_cm, '')::numeric
        * NULLIF(p.product_width_cm, '')::numeric) AS volume_cm3
FROM bronze.products p
LEFT JOIN bronze.product_category_translation t
       ON p.product_category_name = t.product_category_name;

ALTER TABLE silver.products ADD PRIMARY KEY (product_id);

-- ============================================================
-- Orders, with timestamp casting + explicit data-quality flags
-- (bad sequences are FLAGGED, never silently corrected or dropped)
-- ============================================================
CREATE TABLE silver.orders AS
SELECT
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp::timestamp        AS purchase_ts,
    order_approved_at::timestamp               AS approved_ts,
    order_delivered_carrier_date::timestamp    AS carrier_ts,
    order_delivered_customer_date::timestamp   AS delivered_ts,
    order_estimated_delivery_date::timestamp   AS estimated_ts,

    -- flags, one per impossible-sequence rule found in the DQ audit
    (order_status = 'delivered' AND order_delivered_customer_date IS NULL)
        AS is_missing_delivered_date_bug,

    (order_delivered_carrier_date IS NOT NULL AND order_approved_at IS NOT NULL
        AND order_delivered_carrier_date::timestamp < order_approved_at::timestamp)
        AS is_carrier_before_approved,

    (order_delivered_customer_date IS NOT NULL AND order_delivered_carrier_date IS NOT NULL
        AND order_delivered_customer_date::timestamp < order_delivered_carrier_date::timestamp)
        AS is_delivered_before_carrier,

    (order_approved_at IS NOT NULL
        AND order_approved_at::timestamp < order_purchase_timestamp::timestamp)
        AS is_approved_before_purchase,

    -- overall "safe to use in lead-time decomposition" flag
    NOT (
        (order_status = 'delivered' AND order_delivered_customer_date IS NULL)
        OR (order_delivered_carrier_date IS NOT NULL AND order_approved_at IS NOT NULL
            AND order_delivered_carrier_date::timestamp < order_approved_at::timestamp)
        OR (order_delivered_customer_date IS NOT NULL AND order_delivered_carrier_date IS NOT NULL
            AND order_delivered_customer_date::timestamp < order_delivered_carrier_date::timestamp)
        OR (order_approved_at IS NOT NULL
            AND order_approved_at::timestamp < order_purchase_timestamp::timestamp)
    ) AS is_valid_for_lead_time_analysis
FROM bronze.orders;

ALTER TABLE silver.orders ADD PRIMARY KEY (order_id);

-- ============================================================
-- Order items (grain = one product item within one order)
-- ============================================================
CREATE TABLE silver.order_items AS
SELECT
    order_id,
    order_item_id::int AS order_item_id,
    product_id,
    seller_id,
    shipping_limit_date::timestamp AS shipping_limit_ts,
    price::numeric AS price,
    freight_value::numeric AS freight_value
FROM bronze.order_items;

ALTER TABLE silver.order_items ADD PRIMARY KEY (order_id, order_item_id);

-- ============================================================
-- Payments (kept at natural grain: order_id + payment_sequential,
-- an order can be split across several payment methods/installments)
-- ============================================================
CREATE TABLE silver.order_payments AS
SELECT
    order_id,
    payment_sequential::int AS payment_sequential,
    payment_type,
    payment_installments::int AS payment_installments,
    payment_value::numeric AS payment_value
FROM bronze.order_payments;

ALTER TABLE silver.order_payments ADD PRIMARY KEY (order_id, payment_sequential);

-- ============================================================
-- Reviews, deduplicated to one row per order (814 duplicate review_ids /
-- 551 orders had more than one review row in bronze). We keep the review
-- with the latest answer timestamp as the "final" verdict for that order.
-- ============================================================
CREATE TABLE silver.order_reviews AS
SELECT DISTINCT ON (order_id)
    review_id,
    order_id,
    review_score::int AS review_score,
    NULLIF(review_comment_message, '') IS NOT NULL AS has_comment,
    review_creation_date::timestamp AS review_creation_ts,
    review_answer_timestamp::timestamp AS review_answer_ts
FROM bronze.order_reviews
ORDER BY order_id, review_answer_timestamp::timestamp DESC;

ALTER TABLE silver.order_reviews ADD PRIMARY KEY (order_id);

CREATE INDEX idx_silver_order_items_order ON silver.order_items(order_id);
CREATE INDEX idx_silver_order_items_seller ON silver.order_items(seller_id);
CREATE INDEX idx_silver_order_items_product ON silver.order_items(product_id);
CREATE INDEX idx_silver_orders_customer ON silver.orders(customer_id);
