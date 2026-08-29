-- BRONZE LAYER
-- Raw, untyped-as-possible staging tables that mirror the source CSVs 1:1.
-- No cleaning, no dedup, no referential integrity enforced here on purpose:
-- the point of bronze is to preserve exactly what the source system gave us
-- so data-quality issues can be measured against a known baseline.

CREATE SCHEMA IF NOT EXISTS bronze;

DROP TABLE IF EXISTS bronze.customers;
DROP TABLE IF EXISTS bronze.geolocation;
DROP TABLE IF EXISTS bronze.order_items;
DROP TABLE IF EXISTS bronze.order_payments;
DROP TABLE IF EXISTS bronze.order_reviews;
DROP TABLE IF EXISTS bronze.orders;
DROP TABLE IF EXISTS bronze.products;
DROP TABLE IF EXISTS bronze.sellers;
DROP TABLE IF EXISTS bronze.product_category_translation;

CREATE TABLE bronze.customers (
    customer_id                TEXT,
    customer_unique_id         TEXT,
    customer_zip_code_prefix   TEXT,
    customer_city              TEXT,
    customer_state             TEXT
);

CREATE TABLE bronze.geolocation (
    geolocation_zip_code_prefix TEXT,
    geolocation_lat              TEXT,
    geolocation_lng              TEXT,
    geolocation_city             TEXT,
    geolocation_state            TEXT
);

CREATE TABLE bronze.order_items (
    order_id             TEXT,
    order_item_id        TEXT,
    product_id           TEXT,
    seller_id            TEXT,
    shipping_limit_date  TEXT,
    price                TEXT,
    freight_value        TEXT
);

CREATE TABLE bronze.order_payments (
    order_id              TEXT,
    payment_sequential    TEXT,
    payment_type          TEXT,
    payment_installments  TEXT,
    payment_value         TEXT
);

CREATE TABLE bronze.order_reviews (
    review_id                 TEXT,
    order_id                  TEXT,
    review_score              TEXT,
    review_comment_title      TEXT,
    review_comment_message    TEXT,
    review_creation_date      TEXT,
    review_answer_timestamp   TEXT
);

CREATE TABLE bronze.orders (
    order_id                        TEXT,
    customer_id                     TEXT,
    order_status                    TEXT,
    order_purchase_timestamp        TEXT,
    order_approved_at               TEXT,
    order_delivered_carrier_date    TEXT,
    order_delivered_customer_date   TEXT,
    order_estimated_delivery_date   TEXT
);

CREATE TABLE bronze.products (
    product_id                    TEXT,
    product_category_name        TEXT,
    product_name_lenght          TEXT,
    product_description_lenght   TEXT,
    product_photos_qty           TEXT,
    product_weight_g             TEXT,
    product_length_cm            TEXT,
    product_height_cm            TEXT,
    product_width_cm             TEXT
);

CREATE TABLE bronze.sellers (
    seller_id                TEXT,
    seller_zip_code_prefix   TEXT,
    seller_city              TEXT,
    seller_state              TEXT
);

CREATE TABLE bronze.product_category_translation (
    product_category_name          TEXT,
    product_category_name_english  TEXT
);
