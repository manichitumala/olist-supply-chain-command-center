"""Phase 2 - builds the silver layer (cleaned, typed, deduplicated) from bronze."""

from config import ROOT
from db import get_engine, run_sql_file

SCHEMA_SQL = ROOT / "sql" / "silver" / "01_create_silver_schema.sql"


def main():
    run_sql_file(SCHEMA_SQL)
    print("Silver schema built.")

    engine = get_engine()
    with engine.connect() as conn:
        for table in ["customers", "sellers", "products", "orders",
                      "order_items", "order_payments", "order_reviews", "geolocation_zip"]:
            n = conn.exec_driver_sql(f"SELECT COUNT(*) FROM silver.{table}").scalar()
            print(f"  silver.{table:<16} {n:>10,} rows")


if __name__ == "__main__":
    main()
