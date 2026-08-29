"""
Loads the raw Olist CSVs into the bronze schema, unmodified (everything as
text). This is the entry point of the medallion pipeline: raw in, nothing
cleaned, nothing dropped.
"""

from pathlib import Path

import pandas as pd

from config import RAW_DATA_DIR, ROOT
from db import ensure_database_exists, get_engine, run_sql_file

FILE_TO_TABLE = {
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


def main():
    ensure_database_exists()

    schema_sql = ROOT / "sql" / "bronze" / "01_create_bronze_schema.sql"
    run_sql_file(schema_sql)
    print("Bronze schema created.")

    engine = get_engine()

    for filename, table in FILE_TO_TABLE.items():
        path = Path(RAW_DATA_DIR) / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Expected Olist file not found: {path}\n"
                f"Set OLIST_RAW_DIR env var or update config.RAW_DATA_DIR."
            )
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
        df.to_sql(table, engine, schema="bronze", if_exists="append", index=False)
        print(f"Loaded {len(df):>7,} rows -> bronze.{table}")


if __name__ == "__main__":
    main()
