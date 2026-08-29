"""Phase 2/3 - builds the gold star schema (dims + facts) from silver."""

from config import ROOT
from db import get_engine, run_sql_file

SCHEMA_SQL = ROOT / "sql" / "gold" / "01_create_gold_schema.sql"


def main():
    run_sql_file(SCHEMA_SQL)
    print("Gold schema built.")

    engine = get_engine()
    with engine.connect() as conn:
        for table in ["dim_date", "dim_geography", "dim_customer", "dim_seller",
                      "dim_product", "fact_order_item", "fact_delivery"]:
            n = conn.exec_driver_sql(f"SELECT COUNT(*) FROM gold.{table}").scalar()
            print(f"  gold.{table:<18} {n:>10,} rows")


if __name__ == "__main__":
    main()
