"""Gold layer: silver -> star schema (sql/gold), exported to Parquet for BI tools."""

import duckdb

from src.config import ANALYSIS_END, ANALYSIS_START, Settings
from src.db import export_schema_to_parquet, run_sql_file


def build(con: duckdb.DuckDBPyConnection, settings: Settings) -> dict[str, int]:
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    # Single source of truth for the reporting window: config.py -> this table.
    con.execute(
        "CREATE OR REPLACE TABLE gold.analysis_window AS "
        "SELECT CAST(? AS DATE) AS start_date, CAST(? AS DATE) AS end_date",
        [ANALYSIS_START, ANALYSIS_END],
    )
    run_sql_file(con, "gold/01_gold.sql")
    return export_schema_to_parquet(con, "gold", settings.gold_dir)


def main(settings: Settings | None = None):
    from src.config import get_settings
    from src.db import connect

    settings = settings or get_settings()
    with connect(settings) as con:
        for table, n in build(con, settings).items():
            print(f"  gold.{table:<20} {n:>10,} rows")


if __name__ == "__main__":
    main()
