"""Database connection helpers."""

import psycopg2
from sqlalchemy import create_engine

from config import DB_CONFIG, SQLALCHEMY_URL


def get_engine():
    return create_engine(SQLALCHEMY_URL, connect_args={"client_encoding": "utf8"})


def get_psycopg_connection(dbname=None):
    cfg = dict(DB_CONFIG)
    if dbname:
        cfg["dbname"] = dbname
    conn = psycopg2.connect(**cfg)
    conn.set_client_encoding("UTF8")
    return conn


def ensure_database_exists():
    """Creates the target database if it does not already exist."""
    conn = get_psycopg_connection(dbname="postgres")
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_CONFIG["dbname"],))
            if cur.fetchone() is None:
                cur.execute(
                    f'CREATE DATABASE "{DB_CONFIG["dbname"]}" '
                    f"WITH ENCODING 'UTF8' TEMPLATE template0 LC_COLLATE 'C' LC_CTYPE 'C'"
                )
                print(f"Created database {DB_CONFIG['dbname']}")
            else:
                print(f"Database {DB_CONFIG['dbname']} already exists")
    finally:
        conn.close()


def run_sql_file(path):
    """Executes a .sql file that may contain multiple ;-separated statements."""
    sql = path.read_text(encoding="utf-8")
    conn = get_psycopg_connection()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


if __name__ == "__main__":
    ensure_database_exists()
