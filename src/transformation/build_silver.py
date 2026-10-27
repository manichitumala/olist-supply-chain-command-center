"""Silver layer: bronze views -> cleaned, typed, deduplicated tables (sql/silver)."""

import duckdb

from src.config import Settings
from src.db import export_schema_to_parquet, run_sql_file


def build(con: duckdb.DuckDBPyConnection, settings: Settings) -> dict[str, int]:
    run_sql_file(con, "silver/01_silver.sql")
    return export_schema_to_parquet(con, "silver", settings.silver_dir)


def main(settings: Settings | None = None):
    from src.config import get_settings
    from src.db import connect

    settings = settings or get_settings()
    with connect(settings) as con:
        for table, n in build(con, settings).items():
            print(f"  silver.{table:<20} {n:>10,} rows")


if __name__ == "__main__":
    main()
