"""
Bronze layer: raw Olist CSVs -> Parquet, unmodified.

Every column is kept as VARCHAR exactly as the source gave it (typing happens
in silver), plus three lineage columns:
    _source_file, _source_sha256, _ingested_at

Ingestion is incremental at file level: a manifest records each source file's
SHA-256, and a file is only re-ingested when its hash changes or its Parquet
output is missing. The bronze schema in DuckDB is a set of views over the
Parquet files, so the warehouse never holds a second copy of raw data.
"""

import hashlib
import json
from datetime import datetime, timezone

import duckdb

from src.config import SOURCE_FILES, Settings

MANIFEST_NAME = "_manifest.json"


def sha256_of(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest(settings: Settings) -> dict:
    path = settings.bronze_dir / MANIFEST_NAME
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save_manifest(settings: Settings, manifest: dict) -> None:
    path = settings.bronze_dir / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def ingest(con: duckdb.DuckDBPyConnection, settings: Settings, force: bool = False) -> dict:
    """Returns {table: {"rows": int, "status": "ingested" | "unchanged"}}."""
    settings.bronze_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(settings)
    result = {}

    missing = [f for f in SOURCE_FILES if not (settings.raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Olist source files not found in {settings.raw_dir}: {missing}\n"
            "Download the dataset from Kaggle (olistbr/brazilian-ecommerce) and "
            "set OLIST_RAW_DIR to the folder you extracted it to."
        )

    for filename, table in SOURCE_FILES.items():
        src = settings.raw_dir / filename
        out = settings.bronze_dir / f"{table}.parquet"
        digest = sha256_of(src)
        previous = manifest.get(table, {})

        if not force and out.exists() and previous.get("sha256") == digest:
            result[table] = {"rows": previous["rows"], "status": "unchanged"}
            continue

        ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        con.execute(f"""
            COPY (
                SELECT *,
                       '{filename}'      AS _source_file,
                       '{digest}'        AS _source_sha256,
                       TIMESTAMPTZ '{ingested_at}' AS _ingested_at
                FROM read_csv('{src.as_posix()}', all_varchar = true, header = true,
                              delim = ',', quote = '"', escape = '"')
            ) TO '{out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        rows = con.execute(f"SELECT COUNT(*) FROM '{out.as_posix()}'").fetchone()[0]
        manifest[table] = {"sha256": digest, "rows": rows, "ingested_at": ingested_at, "source": filename}
        result[table] = {"rows": rows, "status": "ingested"}

    _save_manifest(settings, manifest)
    create_bronze_views(con, settings)
    return result


def create_bronze_views(con: duckdb.DuckDBPyConnection, settings: Settings) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    for table in SOURCE_FILES.values():
        path = (settings.bronze_dir / f"{table}.parquet").as_posix()
        con.execute(f"CREATE OR REPLACE VIEW bronze.{table} AS SELECT * FROM '{path}'")


def main(settings: Settings | None = None, force: bool = False):
    from src.config import get_settings
    from src.db import connect

    settings = settings or get_settings()
    with connect(settings) as con:
        for table, info in ingest(con, settings, force=force).items():
            print(f"  bronze.{table:<30} {info['rows']:>9,} rows  [{info['status']}]")


if __name__ == "__main__":
    main()
