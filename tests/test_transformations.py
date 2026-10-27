"""Behavioural tests for bronze -> silver -> gold on the synthetic dataset.
Each test pins one rule, most of them v1 bugs."""

import csv
import shutil

import pytest

from src.ingestion import load_bronze


def one(con, sql, params=None):
    return con.execute(sql, params or []).fetchone()


# ---------------------------------------------------------------- bronze

def test_bronze_preserves_raw_rows_and_adds_lineage(synthetic_warehouse):
    con = synthetic_warehouse
    assert one(con, "SELECT COUNT(*) FROM bronze.orders")[0] == 6
    assert one(con, "SELECT COUNT(*) FROM bronze.order_reviews")[0] == 4  # multiline comment parsed
    src, sha = one(con, "SELECT DISTINCT _source_file, _source_sha256 FROM bronze.orders")
    assert src == "olist_orders_dataset.csv" and len(sha) == 64


def test_bronze_keeps_values_as_text(synthetic_warehouse):
    zip_type = one(synthetic_warehouse,
                   "SELECT data_type FROM information_schema.columns "
                   "WHERE table_schema='bronze' AND table_name='customers' "
                   "AND column_name='customer_zip_code_prefix'")[0]
    assert zip_type == "VARCHAR"   # leading zeros of '01001' survive bronze


def test_incremental_ingest_skips_unchanged_and_picks_up_changes(synthetic_settings, tmp_path):
    from src.config import Settings
    from src.db import connect

    raw = tmp_path / "raw"
    shutil.copytree(synthetic_settings.raw_dir, raw)
    settings = Settings(raw_dir=raw, data_dir=tmp_path / "data", reports_dir=tmp_path / "reports")
    with connect(settings) as con:
        first = load_bronze.ingest(con, settings)
        second = load_bronze.ingest(con, settings)
        with open(raw / "olist_sellers_dataset.csv", "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["s3", "20000", "rio de janeiro", "RJ"])
        third = load_bronze.ingest(con, settings)

    assert all(v["status"] == "ingested" for v in first.values())
    assert all(v["status"] == "unchanged" for v in second.values())
    assert third["sellers"] == {"rows": 3, "status": "ingested"}
    assert third["orders"]["status"] == "unchanged"


def test_missing_source_file_fails_loudly(tmp_path):
    from src.config import Settings
    from src.db import connect

    settings = Settings(raw_dir=tmp_path / "empty", data_dir=tmp_path / "d", reports_dir=tmp_path / "r")
    (tmp_path / "empty").mkdir()
    with connect(settings) as con, pytest.raises(FileNotFoundError, match="OLIST_RAW_DIR"):
        load_bronze.ingest(con, settings)


# ---------------------------------------------------------------- silver

def test_review_dedup_keeps_latest_answer(synthetic_warehouse):
    rid, score = one(synthetic_warehouse,
                     "SELECT review_id, review_score FROM silver.order_reviews WHERE order_id='o_due_day'")
    assert (rid, score) == ("r1_new", 5)


def test_untranslated_category_keeps_portuguese_name(synthetic_warehouse):
    rows = dict(synthetic_warehouse.execute(
        "SELECT product_id, category_en FROM silver.products").fetchall())
    assert rows == {"p1": "health_beauty", "p2": "pc_gamer", "p3": "unknown"}


def test_sequence_flags(synthetic_warehouse):
    flags = {r[0]: r[1:] for r in synthetic_warehouse.execute("""
        SELECT order_id, is_carrier_before_approved, is_missing_delivered_date_bug,
               is_valid_for_lead_time_analysis
        FROM silver.orders""").fetchall()}
    assert flags["o_multi"] == (True, False, False)
    assert flags["o_missing"] == (False, True, False)
    assert flags["o_due_day"] == (False, False, True)


def test_geolocation_filters_points_outside_brazil(synthetic_warehouse):
    lat, lon = one(synthetic_warehouse, "SELECT lat, lon FROM silver.geolocation_zip WHERE zip_prefix = 1001")
    assert lat == pytest.approx(-23.555) and lon == pytest.approx(-46.635)


# ---------------------------------------------------------------- gold

def test_on_time_is_judged_on_calendar_date(synthetic_warehouse):
    status = dict(synthetic_warehouse.execute(
        "SELECT order_id, otd_status FROM gold.fact_order").fetchall())
    assert status["o_due_day"] == "On Time"      # delivered 14:00 on the due date
    assert status["o_late_3"] == "Late"
    assert status["o_missing"] == "Not Delivered"
    assert status["o_canceled"] == "Not Delivered"
    assert one(synthetic_warehouse,
               "SELECT days_late FROM gold.fact_order WHERE order_id='o_late_3'")[0] == 1


def test_fact_order_keeps_orders_without_items(synthetic_warehouse):
    has_items, n_items, band = one(synthetic_warehouse,
        "SELECT has_items, n_items, sellers_per_order_band FROM gold.fact_order WHERE order_id='o_noitems'")
    assert (has_items, n_items, band) == (False, 0, "none")
    assert one(synthetic_warehouse, "SELECT COUNT(*) FROM gold.fact_order")[0] == 6


def test_revenue_excludes_cancelled_and_cancel_rate_uses_all_orders(synthetic_warehouse):
    from src.db import query_file
    kpi = query_file(synthetic_warehouse, "kpis/01_executive_kpis.sql", 0).iloc[0]
    # 50 + 60 + 70 + 25: the cancelled order's 100 is excluded
    assert kpi["total_revenue"] == pytest.approx(205.0)
    assert kpi["cancellation_rate_pct"] == pytest.approx(100 / 6, abs=0.01)
    assert kpi["total_orders"] == 6
    assert kpi["unique_customers"] == 5          # c1 and c2 are the same person


def test_seller_metrics_count_orders_not_items(synthetic_warehouse):
    from src.db import query_file
    raw = query_file(synthetic_warehouse, "kpis/04_seller_raw_metrics.sql", 0).set_index("seller_id")
    s1 = raw.loc["s1"]
    # s1: o_due_day (on time), o_late_3 (late, 3 items), o_multi (on time)
    assert s1["n_orders"] == 3 and s1["n_items"] == 5
    assert s1["n_delivered"] == 3 and s1["n_late"] == 1   # v1 item-weighting would give 3 of 5


def test_missed_shipping_limit_uses_sellers_own_deadline(synthetic_warehouse):
    rows = dict(synthetic_warehouse.execute(
        "SELECT order_id || '/' || seller_key, missed_shipping_limit FROM gold.fact_seller_order").fetchall())
    assert rows["o_due_day/s1"] is False         # handed over 03-02 09:00, limit 03-03
    assert rows["o_late_3/s1"] is True           # handed over 04-03 09:00, limit 04-02
    assert rows["o_multi/s1"] is None            # sequence invalid -> not judged


def test_distance_uses_state_centroid_fallback(synthetic_warehouse):
    fallback, state = one(synthetic_warehouse,
        "SELECT is_state_centroid_fallback, state FROM gold.dim_geography WHERE zip_prefix = 99999")
    assert fallback is True and state == "AM"
    d = one(synthetic_warehouse,
            "SELECT distance_km FROM gold.fact_order_item WHERE order_id='o_due_day'")[0]
    assert d == pytest.approx(0.0, abs=1.0)      # same zip for seller and customer


def test_analysis_window_flag(synthetic_warehouse):
    inside = dict(synthetic_warehouse.execute(
        "SELECT order_id, is_in_analysis_window FROM gold.fact_order").fetchall())
    assert inside["o_missing"] is False          # Oct 2016, before the window
    assert inside["o_due_day"] is True


def test_demand_grid_is_complete_with_zero_weeks(synthetic_warehouse):
    from src.db import query_file
    grid = query_file(synthetic_warehouse, "kpis/05_demand_raw.sql")
    n_cat = grid["category_en"].nunique()
    n_weeks = grid["week_start"].nunique()
    assert len(grid) == n_cat * n_weeks
    assert (grid["n_items_sold"] == 0).sum() > 0
    hb = grid[grid["category_en"] == "health_beauty"]["n_items_sold"].sum()
    assert hb == 5                                # o_due_day 1 + o_late_3 3 + o_multi 1
