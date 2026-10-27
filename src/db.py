"""DuckDB connection and SQL-file helpers."""

from pathlib import Path

import duckdb
import pandas as pd

from src.config import SQL_DIR, Settings


def connect(settings: Settings, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(settings.db_path), read_only=read_only)


def split_statements(sql_text: str) -> list[str]:
    """Splits a SQL file on ';' at the end of a code line, ignoring comments.
    Semicolons inside `--` comments are therefore safe."""
    statements, current = [], []
    for line in sql_text.splitlines():
        code = line.split("--", 1)[0].rstrip()
        current.append(line)
        if code.endswith(";"):
            stmt = "\n".join(current).strip()
            # drop leading comment-only lines but keep the statement body
            statements.append(stmt.rstrip(";").strip())
            current = []
    tail = "\n".join(current).strip()
    if tail and any(l.split("--", 1)[0].strip() for l in current):
        statements.append(tail)
    return statements


def read_sql_file(relative_path: str) -> str:
    return (SQL_DIR / relative_path).read_text(encoding="utf-8")


def run_sql_file(con: duckdb.DuckDBPyConnection, relative_path: str) -> None:
    for stmt in split_statements(read_sql_file(relative_path)):
        con.execute(stmt)


def query_file(con: duckdb.DuckDBPyConnection, relative_path: str, index: int = 0) -> pd.DataFrame:
    """Runs the `index`-th statement of a multi-query SQL file."""
    return con.execute(split_statements(read_sql_file(relative_path))[index]).df()


def export_schema_to_parquet(con: duckdb.DuckDBPyConnection, schema: str, out_dir: Path) -> dict[str, int]:
    """Writes every table in `schema` to out_dir/<table>.parquet. These files
    are the hand-off point for Power BI and any other downstream consumer."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = ? AND table_type = 'BASE TABLE' ORDER BY table_name",
        [schema],
    ).fetchall()
    counts = {}
    for (table,) in tables:
        path = (out_dir / f"{table}.parquet").as_posix()
        con.execute(f"COPY {schema}.{table} TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        counts[table] = con.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
    return counts
