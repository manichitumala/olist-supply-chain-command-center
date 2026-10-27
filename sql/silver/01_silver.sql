-- SILVER LAYER (DuckDB)
-- Cleaned, typed, deduplicated tables built from the bronze views.
-- Cleaning rules are a direct response to the bronze data-quality audit
-- (reports/data_quality_report.md). Bad sequences are FLAGGED, never silently
-- corrected or dropped:
--   * 610 products have no category                -> 'unknown'
--   * 13 products have a category missing from the translation file
--     (pc_gamer, portateis_cozinha_...)             -> keep the Portuguese name
--     (v1 silently relabelled these 'unknown')
--   * 1,359 orders: carrier handover < approval     -> flagged
--   * 23 orders: delivered < carrier handover       -> flagged
--   * 8 'delivered' orders with no delivered ts     -> flagged
--   * 814 duplicate review_ids / 551 orders with >1 review -> latest kept
--   * zip prefixes with no geolocation sample       -> state-centroid fallback in gold

CREATE SCHEMA IF NOT EXISTS silver;

-- ============================================================
-- Geolocation: one row per zip prefix. Raw data has many noisy crowd-sourced
-- samples per prefix; filter to Brazil's bounding box, then average.
-- City/state = most frequent value for the prefix.
-- ============================================================
CREATE OR REPLACE TABLE silver.geolocation_zip AS
WITH bounded AS (
    SELECT
        TRY_CAST(geolocation_zip_code_prefix AS INTEGER) AS zip_prefix,
        TRY_CAST(geolocation_lat AS DOUBLE) AS lat,
        TRY_CAST(geolocation_lng AS DOUBLE) AS lon,
        geolocation_city AS city,
        geolocation_state AS state
    FROM bronze.geolocation
    WHERE TRY_CAST(geolocation_lat AS DOUBLE) BETWEEN -33.75 AND 5.27
      AND TRY_CAST(geolocation_lng AS DOUBLE) BETWEEN -73.99 AND -34.79
),
city_mode AS (
    SELECT DISTINCT ON (zip_prefix) zip_prefix, city, state
    FROM (SELECT zip_prefix, city, state, COUNT(*) AS n FROM bounded GROUP BY ALL)
    ORDER BY zip_prefix, n DESC, city, state
)
SELECT b.zip_prefix, AVG(b.lat) AS lat, AVG(b.lon) AS lon, cm.city, cm.state
FROM bounded b
JOIN city_mode cm USING (zip_prefix)
GROUP BY b.zip_prefix, cm.city, cm.state;

-- ============================================================
-- Customers. customer_id is per ORDER in Olist; customer_unique_id is the
-- actual person. Customer analytics must use customer_unique_id.
-- ============================================================
CREATE OR REPLACE TABLE silver.customers AS
SELECT
    customer_id,
    customer_unique_id,
    CAST(customer_zip_code_prefix AS INTEGER) AS zip_prefix,
    customer_city AS city,
    customer_state AS state
FROM bronze.customers;

CREATE OR REPLACE TABLE silver.sellers AS
SELECT
    seller_id,
    CAST(seller_zip_code_prefix AS INTEGER) AS zip_prefix,
    seller_city AS city,
    seller_state AS state
FROM bronze.sellers;

-- ============================================================
-- Products: category translated to English. Missing category -> 'unknown';
-- category with no translation -> the Portuguese name (not 'unknown').
-- ============================================================
CREATE OR REPLACE TABLE silver.products AS
SELECT
    p.product_id,
    COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category_en,
    COALESCE(p.product_category_name, 'unknown') AS category_pt,
    (t.product_category_name_english IS NULL AND p.product_category_name IS NOT NULL)
        AS is_untranslated_category,
    TRY_CAST(p.product_name_lenght AS INTEGER) AS name_length,
    TRY_CAST(p.product_description_lenght AS INTEGER) AS description_length,
    COALESCE(TRY_CAST(p.product_photos_qty AS INTEGER), 0) AS photos_qty,
    TRY_CAST(p.product_weight_g AS DOUBLE) AS weight_g,
    TRY_CAST(p.product_length_cm AS DOUBLE) AS length_cm,
    TRY_CAST(p.product_height_cm AS DOUBLE) AS height_cm,
    TRY_CAST(p.product_width_cm AS DOUBLE) AS width_cm,
    TRY_CAST(p.product_length_cm AS DOUBLE)
        * TRY_CAST(p.product_height_cm AS DOUBLE)
        * TRY_CAST(p.product_width_cm AS DOUBLE) AS volume_cm3
FROM bronze.products p
LEFT JOIN bronze.product_category_translation t USING (product_category_name);

-- ============================================================
-- Orders: typed timestamps + one flag per impossible-sequence rule.
-- ============================================================
CREATE OR REPLACE TABLE silver.orders AS
WITH typed AS (
    SELECT
        order_id,
        customer_id,
        order_status,
        CAST(order_purchase_timestamp AS TIMESTAMP)      AS purchase_ts,
        CAST(order_approved_at AS TIMESTAMP)             AS approved_ts,
        CAST(order_delivered_carrier_date AS TIMESTAMP)  AS carrier_ts,
        CAST(order_delivered_customer_date AS TIMESTAMP) AS delivered_ts,
        CAST(order_estimated_delivery_date AS TIMESTAMP) AS estimated_ts
    FROM bronze.orders
),
flagged AS (
    SELECT *,
        COALESCE(order_status = 'delivered' AND delivered_ts IS NULL, FALSE)
            AS is_missing_delivered_date_bug,
        COALESCE(carrier_ts < approved_ts, FALSE)   AS is_carrier_before_approved,
        COALESCE(delivered_ts < carrier_ts, FALSE)  AS is_delivered_before_carrier,
        COALESCE(approved_ts < purchase_ts, FALSE)  AS is_approved_before_purchase
    FROM typed
)
SELECT *,
    NOT (is_missing_delivered_date_bug OR is_carrier_before_approved
         OR is_delivered_before_carrier OR is_approved_before_purchase)
        AS is_valid_for_lead_time_analysis
FROM flagged;

-- Grain: one product unit within one order.
CREATE OR REPLACE TABLE silver.order_items AS
SELECT
    order_id,
    CAST(order_item_id AS INTEGER) AS order_item_id,
    product_id,
    seller_id,
    CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_ts,
    CAST(price AS DOUBLE) AS price,
    CAST(freight_value AS DOUBLE) AS freight_value
FROM bronze.order_items;

-- Natural grain: order_id + payment_sequential (split payments).
CREATE OR REPLACE TABLE silver.order_payments AS
SELECT
    order_id,
    CAST(payment_sequential AS INTEGER) AS payment_sequential,
    payment_type,
    CAST(payment_installments AS INTEGER) AS payment_installments,
    CAST(payment_value AS DOUBLE) AS payment_value
FROM bronze.order_payments;

-- Reviews: one row per order, latest answered review wins
-- (review_id as a deterministic tie-breaker).
CREATE OR REPLACE TABLE silver.order_reviews AS
SELECT DISTINCT ON (order_id)
    review_id,
    order_id,
    CAST(review_score AS INTEGER) AS review_score,
    NULLIF(TRIM(review_comment_message), '') IS NOT NULL AS has_comment,
    CAST(review_creation_date AS TIMESTAMP) AS review_creation_ts,
    CAST(review_answer_timestamp AS TIMESTAMP) AS review_answer_ts
FROM bronze.order_reviews
ORDER BY order_id, CAST(review_answer_timestamp AS TIMESTAMP) DESC, review_id;
