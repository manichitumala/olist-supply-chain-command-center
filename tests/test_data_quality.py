"""
Data contracts on the silver and gold layers. Every test runs on the
synthetic warehouse, and again on the real one when it has been built.
A failure here means the pipeline produced data that downstream analytics
must not trust.
"""

import pytest

from src.config import ANALYSIS_END, ANALYSIS_START

PRIMARY_KEYS = {
    "silver.orders": ["order_id"],
    "silver.customers": ["customer_id"],
    "silver.sellers": ["seller_id"],
    "silver.products": ["product_id"],
    "silver.order_items": ["order_id", "order_item_id"],
    "silver.order_payments": ["order_id", "payment_sequential"],
    "silver.order_reviews": ["order_id"],
    "silver.geolocation_zip": ["zip_prefix"],
    "gold.dim_date": ["date_id"],
    "gold.dim_geography": ["zip_prefix"],
    "gold.dim_customer": ["customer_key"],
    "gold.dim_seller": ["seller_key"],
    "gold.dim_product": ["product_key"],
    "gold.fact_order_item": ["order_id", "order_item_id"],
    "gold.fact_order": ["order_id"],
    "gold.fact_seller_order": ["order_id", "seller_key"],
}


def scalar(con, sql):
    return con.execute(sql).fetchone()[0]


@pytest.mark.parametrize("table,key", PRIMARY_KEYS.items())
def test_primary_keys_unique_and_not_null(warehouse, table, key):
    cols = ", ".join(key)
    nulls = " OR ".join(f"{c} IS NULL" for c in key)
    assert scalar(warehouse, f"SELECT COUNT(*) - COUNT(DISTINCT ({cols})) FROM {table}") == 0
    assert scalar(warehouse, f"SELECT COUNT(*) FROM {table} WHERE {nulls}") == 0


def test_row_counts_reconcile_across_layers(warehouse):
    con = warehouse
    bronze_orders = scalar(con, "SELECT COUNT(*) FROM bronze.orders")
    assert scalar(con, "SELECT COUNT(*) FROM silver.orders") == bronze_orders
    assert scalar(con, "SELECT COUNT(*) FROM gold.fact_order") == bronze_orders
    bronze_items = scalar(con, "SELECT COUNT(*) FROM bronze.order_items")
    assert scalar(con, "SELECT COUNT(*) FROM gold.fact_order_item") == bronze_items
    assert scalar(con, "SELECT SUM(n_items) FROM gold.fact_seller_order") == bronze_items
    assert scalar(con, "SELECT SUM(n_items) FROM gold.fact_order") == bronze_items


def test_money_reconciles_across_grains(warehouse):
    items = scalar(warehouse, "SELECT SUM(price) FROM gold.fact_order_item")
    orders = scalar(warehouse, "SELECT SUM(items_value) FROM gold.fact_order")
    seller_orders = scalar(warehouse, "SELECT SUM(item_revenue) FROM gold.fact_seller_order")
    assert orders == pytest.approx(items) and seller_orders == pytest.approx(items)


def test_every_item_resolves_to_dimensions(warehouse):
    orphans = scalar(warehouse, """
        SELECT COUNT(*) FROM gold.fact_order_item f
        LEFT JOIN gold.dim_product p ON p.product_key = f.product_key
        LEFT JOIN gold.dim_seller s ON s.seller_key = f.seller_key
        LEFT JOIN gold.dim_customer c ON c.customer_key = f.customer_key
        WHERE p.product_key IS NULL OR s.seller_key IS NULL OR c.customer_key IS NULL""")
    assert orphans == 0


def test_otd_status_domain_and_consistency(warehouse):
    assert scalar(warehouse, """
        SELECT COUNT(*) FROM gold.fact_order
        WHERE otd_status NOT IN ('On Time', 'Late', 'Not Delivered')""") == 0
    assert scalar(warehouse, """
        SELECT COUNT(*) FROM gold.fact_order
        WHERE (otd_status = 'Late') <> COALESCE(days_late > 0, FALSE)""") == 0
    assert scalar(warehouse, """
        SELECT COUNT(*) FROM gold.fact_order
        WHERE (otd_status <> 'Not Delivered') <> is_delivered""") == 0


def test_lead_time_stages_non_negative_when_valid(warehouse):
    assert scalar(warehouse, """
        SELECT COUNT(*) FROM gold.fact_order
        WHERE is_valid_for_lead_time_analysis
          AND (payment_time_hours < 0 OR fulfilment_time_hours < 0
               OR transit_time_hours < 0 OR lead_time_days < 0)""") == 0


def test_value_ranges(warehouse):
    assert scalar(warehouse, "SELECT COUNT(*) FROM silver.order_reviews WHERE review_score NOT BETWEEN 1 AND 5") == 0
    assert scalar(warehouse, "SELECT COUNT(*) FROM silver.order_items WHERE price <= 0 OR freight_value < 0") == 0
    assert scalar(warehouse, "SELECT COUNT(*) FROM gold.fact_order_item WHERE distance_km < 0 OR distance_km > 5000") == 0


def test_analysis_window_matches_config(warehouse):
    start, end = warehouse.execute("SELECT start_date, end_date FROM gold.analysis_window").fetchone()
    assert (start, end) == (ANALYSIS_START, ANALYSIS_END)


# --------------------------------------------- real-data regression guards

def test_real_headline_kpis(real_warehouse):
    """Pins the corrected v2 headline figures quoted in the README."""
    row = real_warehouse.execute("""
        SELECT COUNT(*),
               COUNT(DISTINCT customer_unique_id),
               ROUND(100.0 * AVG(CASE WHEN is_delivered THEN (otd_status = 'On Time')::INT END), 2),
               ROUND(100.0 * AVG(is_canceled::INT), 2),
               SUM((NOT has_items)::INT)
        FROM gold.fact_order""").fetchone()
    assert row == (99441, 96096, 93.23, 0.63, 775)
