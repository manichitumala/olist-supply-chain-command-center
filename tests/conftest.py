"""
Shared fixtures.

`synthetic_warehouse` builds bronze -> silver -> gold from a tiny hand-made
Olist dataset in which every row exists to exercise one rule (see
SCENARIOS). It needs no Kaggle download, so the whole suite runs in CI.

`real_warehouse` points at data/warehouse.duckdb when the full pipeline has
been run locally; tests using it are skipped otherwise.
"""

import csv
from pathlib import Path

import duckdb
import pytest

from src.config import ROOT, Settings

SCENARIOS = {
    "o_due_day":   "delivered at 14:00 ON the estimated date -> On Time (v1 said Late)",
    "o_late_3":    "3 items from one seller, delivered a day late -> counts once for that seller",
    "o_canceled":  "cancelled with an item -> excluded from revenue, counted in cancel rate",
    "o_noitems":   "unavailable with no items -> still present in fact_order",
    "o_multi":     "two sellers; carrier handover before approval -> lead-time flag",
    "o_missing":   "status delivered but no delivered timestamp -> data bug flag",
}

HEADERS = {
    "olist_customers_dataset.csv": ["customer_id", "customer_unique_id", "customer_zip_code_prefix",
                                    "customer_city", "customer_state"],
    "olist_geolocation_dataset.csv": ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng",
                                      "geolocation_city", "geolocation_state"],
    "olist_order_items_dataset.csv": ["order_id", "order_item_id", "product_id", "seller_id",
                                      "shipping_limit_date", "price", "freight_value"],
    "olist_order_payments_dataset.csv": ["order_id", "payment_sequential", "payment_type",
                                         "payment_installments", "payment_value"],
    "olist_order_reviews_dataset.csv": ["review_id", "order_id", "review_score", "review_comment_title",
                                        "review_comment_message", "review_creation_date",
                                        "review_answer_timestamp"],
    "olist_orders_dataset.csv": ["order_id", "customer_id", "order_status", "order_purchase_timestamp",
                                 "order_approved_at", "order_delivered_carrier_date",
                                 "order_delivered_customer_date", "order_estimated_delivery_date"],
    "olist_products_dataset.csv": ["product_id", "product_category_name", "product_name_lenght",
                                   "product_description_lenght", "product_photos_qty", "product_weight_g",
                                   "product_length_cm", "product_height_cm", "product_width_cm"],
    "olist_sellers_dataset.csv": ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
    "product_category_name_translation.csv": ["product_category_name", "product_category_name_english"],
}

ROWS = {
    "olist_customers_dataset.csv": [
        ["c1", "u1", "01001", "sao paulo", "SP"],
        ["c2", "u1", "01001", "sao paulo", "SP"],          # same person as c1
        ["c3", "u3", "20000", "rio de janeiro", "RJ"],
        ["c4", "u4", "20000", "rio de janeiro", "RJ"],
        ["c5", "u5", "69000", "manaus", "AM"],
        ["c6", "u6", "99999", "nowhere", "AM"],            # zip with no geolocation
    ],
    "olist_geolocation_dataset.csv": [
        ["01001", "-23.55", "-46.63", "sao paulo", "SP"],
        ["01001", "-23.56", "-46.64", "sao paulo", "SP"],
        ["20000", "-22.90", "-43.20", "rio de janeiro", "RJ"],
        ["69000", "-3.10", "-60.02", "manaus", "AM"],
        ["30000", "-19.92", "-43.94", "belo horizonte", "MG"],
        ["01001", "48.85", "2.35", "paris", "SP"],         # outside Brazil -> filtered
    ],
    "olist_orders_dataset.csv": [
        ["o_due_day", "c1", "delivered", "2017-03-01 10:00:00", "2017-03-01 11:00:00",
         "2017-03-02 09:00:00", "2017-03-10 14:00:00", "2017-03-10 00:00:00"],
        ["o_late_3", "c2", "delivered", "2017-04-01 10:00:00", "2017-04-01 10:30:00",
         "2017-04-03 09:00:00", "2017-04-11 08:00:00", "2017-04-10 00:00:00"],
        ["o_canceled", "c3", "canceled", "2017-05-01 10:00:00", "2017-05-01 10:10:00", "", "",
         "2017-05-20 00:00:00"],
        ["o_noitems", "c4", "unavailable", "2017-05-02 10:00:00", "2017-05-02 10:10:00", "", "",
         "2017-05-25 00:00:00"],
        ["o_multi", "c5", "delivered", "2017-06-01 10:00:00", "2017-06-02 10:00:00",
         "2017-06-01 18:00:00", "2017-06-20 10:00:00", "2017-06-25 00:00:00"],
        ["o_missing", "c6", "delivered", "2016-10-05 10:00:00", "2016-10-05 11:00:00",
         "2016-10-07 10:00:00", "", "2016-10-30 00:00:00"],
    ],
    "olist_order_items_dataset.csv": [
        ["o_due_day", "1", "p1", "s1", "2017-03-03 00:00:00", "50.00", "10.00"],
        ["o_late_3", "1", "p1", "s1", "2017-04-02 00:00:00", "20.00", "5.00"],
        ["o_late_3", "2", "p1", "s1", "2017-04-02 00:00:00", "20.00", "5.00"],
        ["o_late_3", "3", "p1", "s1", "2017-04-02 00:00:00", "20.00", "5.00"],
        ["o_canceled", "1", "p2", "s2", "2017-05-03 00:00:00", "100.00", "15.00"],
        ["o_multi", "1", "p1", "s1", "2017-06-03 00:00:00", "30.00", "8.00"],
        ["o_multi", "2", "p3", "s2", "2017-06-03 00:00:00", "40.00", "9.00"],
        ["o_missing", "1", "p2", "s2", "2016-10-08 00:00:00", "25.00", "6.00"],
    ],
    "olist_order_payments_dataset.csv": [
        ["o_due_day", "1", "credit_card", "1", "60.00"],
        ["o_late_3", "1", "credit_card", "2", "50.00"],
        ["o_late_3", "2", "voucher", "1", "25.00"],
        ["o_canceled", "1", "boleto", "1", "115.00"],
        ["o_multi", "1", "credit_card", "3", "87.00"],
        ["o_missing", "1", "credit_card", "1", "31.00"],
    ],
    "olist_order_reviews_dataset.csv": [
        ["r1_old", "o_due_day", "2", "", "first", "2017-03-11 00:00:00", "2017-03-11 10:00:00"],
        ["r1_new", "o_due_day", "5", "", "second, final", "2017-03-12 00:00:00", "2017-03-12 10:00:00"],
        ["r2", "o_late_3", "3", "", "", "2017-04-12 00:00:00", "2017-04-12 10:00:00"],
        ["r5", "o_multi", "1", "", "split delivery\nsecond line", "2017-06-21 00:00:00", "2017-06-21 10:00:00"],
    ],
    "olist_products_dataset.csv": [
        ["p1", "beleza_saude", "40", "300", "2", "500", "20", "10", "15"],
        ["p2", "pc_gamer", "35", "250", "1", "2000", "40", "20", "30"],   # no translation
        ["p3", "", "", "", "", "100", "10", "10", "10"],                   # no category
    ],
    "olist_sellers_dataset.csv": [
        ["s1", "01001", "sao paulo", "SP"],
        ["s2", "30000", "belo horizonte", "MG"],
    ],
    "product_category_name_translation.csv": [
        ["beleza_saude", "health_beauty"],
    ],
}


def write_synthetic_raw(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for filename, header in HEADERS.items():
        with open(raw_dir / filename, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            w.writerow(header)
            w.writerows(ROWS[filename])


def build_warehouse(settings: Settings) -> duckdb.DuckDBPyConnection:
    from src.db import connect
    from src.ingestion import load_bronze
    from src.transformation import build_gold, build_silver

    con = connect(settings)
    load_bronze.ingest(con, settings)
    build_silver.build(con, settings)
    build_gold.build(con, settings)
    return con


@pytest.fixture(scope="session")
def synthetic_settings(tmp_path_factory) -> Settings:
    base = tmp_path_factory.mktemp("olist")
    settings = Settings(raw_dir=base / "raw", data_dir=base / "data", reports_dir=base / "reports")
    write_synthetic_raw(settings.raw_dir)
    return settings


@pytest.fixture(scope="session")
def synthetic_warehouse(synthetic_settings):
    con = build_warehouse(synthetic_settings)
    yield con
    con.close()


@pytest.fixture(scope="session")
def real_warehouse():
    path = ROOT / "data" / "warehouse.duckdb"
    if not path.exists():
        pytest.skip("real warehouse not built (run `python -m src.pipeline`)")
    con = duckdb.connect(str(path), read_only=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM gold.fact_order").fetchone()[0]
    except duckdb.Error:
        con.close()
        pytest.skip("real warehouse has no gold layer")
    if n < 90_000:
        con.close()
        pytest.skip("warehouse does not hold the full Olist dataset")
    yield con
    con.close()


@pytest.fixture(scope="session", params=["synthetic", "real"])
def warehouse(request):
    """Runs a test against both warehouses (real one skipped when absent)."""
    return request.getfixturevalue(f"{request.param}_warehouse")
