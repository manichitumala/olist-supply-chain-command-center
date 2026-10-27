"""
Central configuration.

Every path can be overridden with an environment variable so the same code
runs locally, in Docker and in CI (where tests point it at a tiny synthetic
dataset instead of the real Kaggle files).
"""

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"

# The 9 source files of the Olist Kaggle dataset -> bronze table names.
SOURCE_FILES = {
    "olist_customers_dataset.csv": "customers",
    "olist_geolocation_dataset.csv": "geolocation",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_orders_dataset.csv": "orders",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "product_category_translation",
}

# Reporting window for anything trended over time. The raw data runs from
# 2016-09-04 to 2018-10-17, but 2016 has a gap (no orders in Nov, 1 in Dec)
# and Sep/Oct 2018 hold only 20 orders, almost all cancelled. Including those
# months produces fake demand "drops" and meaningless monthly rates.
ANALYSIS_START = date(2017, 1, 1)
ANALYSIS_END = date(2018, 8, 31)

# Minimum distinct orders before a seller is ranked. Below this the 95%
# confidence interval on a late rate is wider than ~+/-10 points.
MIN_SELLER_ORDERS = 30


@dataclass(frozen=True)
class Settings:
    raw_dir: Path
    data_dir: Path
    reports_dir: Path

    @property
    def bronze_dir(self) -> Path:
        return self.data_dir / "bronze"

    @property
    def silver_dir(self) -> Path:
        return self.data_dir / "silver"

    @property
    def gold_dir(self) -> Path:
        return self.data_dir / "gold"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "warehouse.duckdb"

    @property
    def charts_dir(self) -> Path:
        return self.reports_dir / "charts"


def get_settings() -> Settings:
    return Settings(
        raw_dir=Path(os.environ.get("OLIST_RAW_DIR", ROOT / "data" / "raw")),
        data_dir=Path(os.environ.get("OLIST_DATA_DIR", ROOT / "data")),
        reports_dir=Path(os.environ.get("OLIST_REPORTS_DIR", ROOT / "reports")),
    )
