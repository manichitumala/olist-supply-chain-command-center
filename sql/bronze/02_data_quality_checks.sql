-- BRONZE LAYER DATA QUALITY CHECKS
-- Every query here is designed to be run standalone and read top-to-bottom
-- as a data quality audit. python/data_quality.py runs these and compiles
-- the results into reports/data_quality_report.md.

-- ============================================================
-- 1. COMPLETENESS: COUNT(*) - COUNT(column) per critical column
-- ============================================================

-- 1a. Products missing a category name
SELECT COUNT(*) AS total_products,
       COUNT(*) - COUNT(product_category_name) AS missing_category
FROM bronze.products;

-- 1b. Orders missing key lifecycle timestamps
SELECT
    COUNT(*) AS total_orders,
    COUNT(*) - COUNT(order_approved_at)             AS missing_approved_at,
    COUNT(*) - COUNT(order_delivered_carrier_date)   AS missing_carrier_date,
    COUNT(*) - COUNT(order_delivered_customer_date)  AS missing_delivered_date,
    COUNT(*) - COUNT(order_estimated_delivery_date)  AS missing_estimated_date
FROM bronze.orders;

-- 1c. Orders missing timestamps, broken down by order_status
-- (explains WHY they're missing: undelivered/cancelled orders are expected
--  to have nulls; a 'delivered' order with a null delivered date is a bug)
SELECT
    order_status,
    COUNT(*) AS n_orders,
    COUNT(*) - COUNT(order_delivered_customer_date) AS missing_delivered_date
FROM bronze.orders
GROUP BY order_status
ORDER BY n_orders DESC;

-- 1d. Reviews missing score or comment text
SELECT
    COUNT(*) AS total_reviews,
    COUNT(*) - COUNT(review_score) AS missing_score,
    COUNT(*) - COUNT(NULLIF(review_comment_message, '')) AS missing_comment_message
FROM bronze.order_reviews;

-- 1e. Geolocation coverage: zip prefixes with no geolocation row at all
SELECT COUNT(DISTINCT c.customer_zip_code_prefix) AS customer_zips_without_geo
FROM bronze.customers c
LEFT JOIN bronze.geolocation g
       ON c.customer_zip_code_prefix = g.geolocation_zip_code_prefix
WHERE g.geolocation_zip_code_prefix IS NULL;

-- 1f. Seller zip prefixes with no geolocation row at all
SELECT COUNT(DISTINCT s.seller_zip_code_prefix) AS seller_zips_without_geo
FROM bronze.sellers s
LEFT JOIN bronze.geolocation g
       ON s.seller_zip_code_prefix = g.geolocation_zip_code_prefix
WHERE g.geolocation_zip_code_prefix IS NULL;

-- ============================================================
-- 2. REFERENTIAL INTEGRITY
-- ============================================================

-- 2a. Orders without a matching customer
SELECT COUNT(*) AS orders_without_customer
FROM bronze.orders o
LEFT JOIN bronze.customers c ON o.customer_id = c.customer_id
WHERE c.customer_id IS NULL;

-- 2b. Order items without a matching product
SELECT COUNT(*) AS order_items_without_product
FROM bronze.order_items oi
LEFT JOIN bronze.products p ON oi.product_id = p.product_id
WHERE p.product_id IS NULL;

-- 2c. Order items without a matching seller
SELECT COUNT(*) AS order_items_without_seller
FROM bronze.order_items oi
LEFT JOIN bronze.sellers s ON oi.seller_id = s.seller_id
WHERE s.seller_id IS NULL;

-- 2d. Order items without a matching order
SELECT COUNT(*) AS order_items_without_order
FROM bronze.order_items oi
LEFT JOIN bronze.orders o ON oi.order_id = o.order_id
WHERE o.order_id IS NULL;

-- 2e. Payments without a matching order
SELECT COUNT(*) AS payments_without_order
FROM bronze.order_payments op
LEFT JOIN bronze.orders o ON op.order_id = o.order_id
WHERE o.order_id IS NULL;

-- 2f. Reviews without a matching order
SELECT COUNT(*) AS reviews_without_order
FROM bronze.order_reviews r
LEFT JOIN bronze.orders o ON r.order_id = o.order_id
WHERE o.order_id IS NULL;

-- ============================================================
-- 3. DUPLICATES
-- ============================================================

SELECT 'orders' AS table_name, COUNT(*) - COUNT(DISTINCT order_id) AS duplicate_keys FROM bronze.orders
UNION ALL
SELECT 'customers', COUNT(*) - COUNT(DISTINCT customer_id) FROM bronze.customers
UNION ALL
SELECT 'products', COUNT(*) - COUNT(DISTINCT product_id) FROM bronze.products
UNION ALL
SELECT 'sellers', COUNT(*) - COUNT(DISTINCT seller_id) FROM bronze.sellers
UNION ALL
SELECT 'order_items', COUNT(*) - COUNT(DISTINCT order_id || '-' || order_item_id) FROM bronze.order_items
UNION ALL
SELECT 'order_reviews (review_id)', COUNT(*) - COUNT(DISTINCT review_id) FROM bronze.order_reviews
UNION ALL
SELECT 'order_reviews (order_id, duplicated reviews per order)',
       COUNT(*) - COUNT(DISTINCT order_id) FROM bronze.order_reviews;

-- ============================================================
-- 4. TIMESTAMP / SEQUENCE VALIDATION
-- Purchase -> Approved -> Carrier handover -> Delivered
-- ============================================================

-- 4a. Payment approved before the order was even purchased
SELECT COUNT(*) AS approved_before_purchase
FROM bronze.orders
WHERE order_approved_at IS NOT NULL
  AND order_approved_at::timestamp < order_purchase_timestamp::timestamp;

-- 4b. Carrier handover before payment was approved
SELECT COUNT(*) AS carrier_before_approved
FROM bronze.orders
WHERE order_delivered_carrier_date IS NOT NULL
  AND order_approved_at IS NOT NULL
  AND order_delivered_carrier_date::timestamp < order_approved_at::timestamp;

-- 4c. Customer delivery before carrier handover
SELECT COUNT(*) AS delivered_before_carrier_handover
FROM bronze.orders
WHERE order_delivered_customer_date IS NOT NULL
  AND order_delivered_carrier_date IS NOT NULL
  AND order_delivered_customer_date::timestamp < order_delivered_carrier_date::timestamp;

-- 4d. Customer delivery before purchase (the most basic impossible sequence)
SELECT COUNT(*) AS delivered_before_purchase
FROM bronze.orders
WHERE order_delivered_customer_date IS NOT NULL
  AND order_delivered_customer_date::timestamp < order_purchase_timestamp::timestamp;

-- 4e. Estimated delivery date earlier than purchase date (suspicious metadata)
SELECT COUNT(*) AS estimated_before_purchase
FROM bronze.orders
WHERE order_estimated_delivery_date IS NOT NULL
  AND order_estimated_delivery_date::timestamp < order_purchase_timestamp::timestamp;

-- ============================================================
-- 5. VALUE RANGE / SANITY CHECKS
-- ============================================================

-- 5a. Non-positive price or freight value
SELECT
    SUM(CASE WHEN price::numeric <= 0 THEN 1 ELSE 0 END) AS non_positive_price,
    SUM(CASE WHEN freight_value::numeric < 0 THEN 1 ELSE 0 END) AS negative_freight
FROM bronze.order_items;

-- 5b. Review scores outside the valid 1-5 range
SELECT COUNT(*) AS invalid_review_scores
FROM bronze.order_reviews
WHERE review_score::int NOT BETWEEN 1 AND 5;

-- 5c. Negative payment values
SELECT COUNT(*) AS negative_payments
FROM bronze.order_payments
WHERE payment_value::numeric < 0;
